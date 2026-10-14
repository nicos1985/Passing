import os
import re
import smtplib
import unicodedata
from datetime import timedelta
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.db import connection, models, transaction
from django.utils import timezone
from django.urls import reverse
from notifications.service import record_email_notice

from .models import CheckResult, Delivery, Incident


BITRIX_CLIENT_FIELD = "UF_CRM_1751302650"  # "Cuenta" in this portal's API
BITRIX_CLIENT_OPTION_ID = 7258  # "MONITOR PASSING"

SAFE_BITRIX_ERRORS = {
    "Webhook Bitrix24 HTTPS no configurado",
    "Bitrix24 no pudo buscar negociaciones existentes",
    "Bitrix24 rechazó la negociación",
    "Bitrix24 no devolvió el ID de negociación",
    "Bitrix24 rechazó la consulta CRM",
    "Bitrix24 no devolvió los campos de negociación",
    "Bitrix24 no tiene un campo de criticidad con la opción Crítica",
    "Bitrix24 rechazó la consulta de la negociación",
    "Bitrix24 no devolvió el estado de la negociación",
}


def _require_smtp_config():
    if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend" or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        raise RuntimeError("SMTP no configurado")


def delivery_error_message(error, channel):
    """Keep diagnostic messages useful without persisting URLs or credentials."""
    if isinstance(error, str):
        if error == "SMTPAuthenticationError":
            return "Autenticación SMTP rechazada. Revisá usuario y contraseña de correo."
        if error == "RuntimeError":
            return "Bitrix24 no completó el envío. Reintentá tras revisar el webhook y sus permisos."
        return error
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "Autenticación SMTP rechazada. Revisá usuario y contraseña de correo."
    if isinstance(error, smtplib.SMTPException):
        return f"Error SMTP ({type(error).__name__}). Revisá la configuración del servidor de correo."
    if isinstance(error, (requests.exceptions.Timeout, TimeoutError)):
        return f"Tiempo de espera agotado al conectar con {'Bitrix24' if channel == Delivery.Channel.BITRIX else 'SMTP'}."
    if isinstance(error, requests.exceptions.HTTPError):
        code = error.response.status_code if error.response is not None else None
        return f"Bitrix24 respondió HTTP {code}." if code else "Bitrix24 rechazó la solicitud HTTP."
    if isinstance(error, requests.exceptions.ConnectionError):
        return "No se pudo conectar con Bitrix24."
    if isinstance(error, RuntimeError) and str(error) in SAFE_BITRIX_ERRORS:
        return str(error)
    if isinstance(error, RuntimeError) and str(error) == "SMTP no configurado":
        return str(error)
    if isinstance(error, RuntimeError) and str(error) == "SMTP no aceptó el correo de prueba":
        return str(error)
    return f"Error de {'Bitrix24' if channel == Delivery.Channel.BITRIX else 'correo'} ({type(error).__name__})."


def test_smtp_connection():
    _require_smtp_config()
    connection = get_connection(timeout=5)
    try:
        connection.open()
    finally:
        connection.close()


def send_test_email(address):
    _require_smtp_config()
    sent = send_mail(
        "[Monitorización] Correo de prueba",
        "Este es un correo de prueba del módulo de monitorización de Passing.",
        settings.DEFAULT_FROM_EMAIL,
        [address],
        fail_silently=False,
        connection=get_connection(timeout=10),
    )
    if sent != 1:
        raise RuntimeError("SMTP no aceptó el correo de prueba")


def test_bitrix_connection():
    webhook = os.getenv("MONITORING_BITRIX_WEBHOOK_URL", "").rstrip("/")
    if not webhook.startswith("https://"):
        raise RuntimeError("Webhook Bitrix24 HTTPS no configurado")
    _bitrix_incident_fields(webhook, "[Monitorización] Prueba")


def bitrix_deal_url(deal_id):
    """Build a public UI link without exposing the webhook credential."""
    if not re.fullmatch(r"[0-9]+", str(deal_id)):
        return None
    webhook = urlsplit(os.getenv("MONITORING_BITRIX_WEBHOOK_URL", ""))
    if webhook.scheme != "https" or not webhook.hostname or webhook.username or webhook.password:
        return None
    return f"https://{webhook.hostname}/crm/deal/details/{deal_id}/"


def _incident_reason(incident):
    result = CheckResult.objects.filter(monitor=incident.monitor, checked_at__gte=incident.started_at).order_by("checked_at").first()
    return result.detail if result else ""


def _field_label(value):
    return "".join(char for char in unicodedata.normalize("NFKD", str(value).casefold()) if not unicodedata.combining(char)).strip()


def _bitrix_incident_fields(webhook, title):
    response = requests.post(
        f"{webhook}/crm.item.fields.json",
        json={"entityTypeId": 2, "useOriginalUfNames": "Y"}, timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    fields = data.get("result", {}).get("fields")
    if "error" in data or not isinstance(fields, dict):
        raise RuntimeError("Bitrix24 no devolvió los campos de negociación")
    extra = {}
    criticality_found = False
    for key, field in fields.items():
        if not key.startswith("UF_") or not isinstance(field, dict) or field.get("isReadOnly"):
            continue
        labels = {_field_label(field.get(name, "")) for name in ("title", "formLabel", "listLabel", "upperName")}
        if "asunto" in labels and field.get("type") in {"string", "text"}:
            extra[key] = title
        if "criticidad" in labels or "criticality" in labels:
            if field.get("type") == "enumeration":
                for option in field.get("items", []):
                    if _field_label(option.get("VALUE", "")) in {"critica", "critical"} and option.get("ID"):
                        extra[key] = int(option["ID"])
                        criticality_found = True
                        break
            elif field.get("type") in {"string", "text"}:
                extra[key] = "Crítica"
                criticality_found = True
    if not criticality_found:
        raise RuntimeError("Bitrix24 no tiene un campo de criticidad con la opción Crítica")
    return extra


def _send_email(delivery):
    incident = delivery.incident
    monitor = incident.monitor
    recipients = monitor.recipients_list
    if not recipients:
        return
    recovered = delivery.event == "recovered"
    subject = f"[Monitorización] {'Recuperado' if recovered else 'Caído'}: {monitor.name}"
    message = (
        f"Servicio: {monitor.name}\nDestino: {monitor.host}\n"
        f"Incidente: {incident.pk}\nInicio: {incident.started_at.isoformat()}\n"
        f"Estado: {'recuperado' if recovered else 'caído'}\n"
    )
    if not recovered:
        message += f"Motivo: {_incident_reason(incident)}\n"
    sent = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, connection=get_connection(timeout=10))
    if sent:
        record_email_notice(
            recipients, category='monitoring', source_id=incident.pk, event=delivery.event,
            title='Incidente de monitorización' if delivery.event == 'opened' else 'Servicio recuperado',
            target_path=reverse('monitoring:incident', args=[incident.pk], urlconf='passing.urls_tenant'),
            permissions=('monitoring.manage_monitoring', 'monitoring.read_monitoring'),
        )


def _send_bitrix(delivery):
    incident = delivery.incident
    if incident.bitrix_deal_id:
        return
    webhook = os.getenv("MONITORING_BITRIX_WEBHOOK_URL", "").rstrip("/")
    if not webhook.startswith("https://"):
        raise RuntimeError("Webhook Bitrix24 HTTPS no configurado")
    title = f"[Monitorización] {incident.monitor.name} caído (incidente {incident.pk})"
    origin_id = f"{connection.schema_name}:{incident.pk}"
    list_response = requests.post(
        f"{webhook}/crm.item.list.json",
        json={"entityTypeId": 2, "filter": {"originatorId": "passing-monitoring", "originId": origin_id}, "select": ["id"]},
        timeout=5,
    )
    list_response.raise_for_status()
    existing = list_response.json()
    if "error" in existing:
        raise RuntimeError("Bitrix24 no pudo buscar negociaciones existentes")
    items = existing.get("result", {}).get("items", [])
    if items:
        incident.bitrix_deal_id = str(items[0]["id"])
        incident.bitrix_error = ""
        incident.save(update_fields=["bitrix_deal_id", "bitrix_error"])
        return
    extra_fields = _bitrix_incident_fields(webhook, title)
    payload = {
        "entityTypeId": 2,
        "useOriginalUfNames": "Y",
        "fields": {
            "title": title,
            "categoryId": 174,
            "originatorId": "passing-monitoring",
            "originId": origin_id,
            BITRIX_CLIENT_FIELD: BITRIX_CLIENT_OPTION_ID,
            **extra_fields,
            "comments": f"Destino: {incident.monitor.host}\nInicio: {incident.started_at.isoformat()}\nMotivo: {_incident_reason(incident)}\nIncidente interno: {incident.pk}",
        },
    }
    response = requests.post(f"{webhook}/crm.item.add.json", json=payload, timeout=5)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError("Bitrix24 rechazó la negociación")
    deal_id = data.get("result", {}).get("item", {}).get("id")
    if not deal_id:
        raise RuntimeError("Bitrix24 no devolvió el ID de negociación")
    incident.bitrix_deal_id = str(deal_id)
    incident.bitrix_error = ""
    incident.save(update_fields=["bitrix_deal_id", "bitrix_error"])


def sync_bitrix_resolutions(limit=10):
    """Refresh deal closure without changing the technical recovery state."""
    webhook = os.getenv("MONITORING_BITRIX_WEBHOOK_URL", "").rstrip("/")
    if not webhook.startswith("https://"):
        return
    now = timezone.now()
    due = Incident.objects.filter(bitrix_deal_id__regex=r"^[0-9]+$").filter(
        models.Q(bitrix_synced_at__isnull=True) | models.Q(bitrix_synced_at__lte=now - timedelta(minutes=5))
    ).order_by("bitrix_synced_at", "pk")[:limit]
    for incident in due:
        try:
            response = requests.post(
                f"{webhook}/crm.item.get.json",
                json={"entityTypeId": 2, "id": int(incident.bitrix_deal_id)}, timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            item = data.get("result", {}).get("item")
            if "error" in data or not isinstance(item, dict):
                raise RuntimeError("Bitrix24 rechazó la consulta de la negociación")
            closed = item.get("closed")
            if closed not in (True, False, "Y", "N", 1, 0):
                raise RuntimeError("Bitrix24 no devolvió el estado de la negociación")
            is_closed = closed in (True, "Y", 1)
            incident.bitrix_resolved_at = (incident.bitrix_resolved_at or now) if is_closed else None
            incident.bitrix_sync_error = ""
        except Exception as exc:
            incident.bitrix_sync_error = delivery_error_message(exc, Delivery.Channel.BITRIX)[:240]
        incident.bitrix_synced_at = timezone.now()
        incident.save(update_fields=["bitrix_resolved_at", "bitrix_sync_error", "bitrix_synced_at"])


def deliver_pending(limit=3):
    now = timezone.now()
    Delivery.objects.filter(status="sending", next_attempt_at__lte=now).update(status="pending")
    ids = list(Delivery.objects.filter(status="pending", next_attempt_at__lte=now).order_by("created_at").values_list("pk", flat=True)[:limit])
    for delivery_id in ids:
        with transaction.atomic():
            delivery = Delivery.objects.select_for_update().select_related("incident__monitor").get(pk=delivery_id)
            if delivery.status != "pending":
                continue
            delivery.status = "sending"
            delivery.next_attempt_at = timezone.now() + timedelta(minutes=10)
            delivery.save(update_fields=["status", "next_attempt_at"])
        try:
            if delivery.channel == Delivery.Channel.EMAIL:
                _send_email(delivery)
            else:
                _send_bitrix(delivery)
        except Exception as exc:
            # Never log request URLs or response bodies: webhook URLs contain secrets.
            delivery.attempts += 1
            delivery.last_error = delivery_error_message(exc, delivery.channel)[:240]
            delivery.status = "pending" if delivery.attempts < 10 else "failed"
            delivery.next_attempt_at = timezone.now() + timedelta(minutes=min(2 ** delivery.attempts, 60))
            delivery.save(update_fields=["attempts", "last_error", "status", "next_attempt_at"])
            if delivery.channel == Delivery.Channel.BITRIX:
                Incident.objects.filter(pk=delivery.incident_id).update(bitrix_error=delivery.last_error)
        else:
            delivery.status = "sent"
            delivery.sent_at = timezone.now()
            delivery.last_error = ""
            delivery.save(update_fields=["status", "sent_at", "last_error"])
