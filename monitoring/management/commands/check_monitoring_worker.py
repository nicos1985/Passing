"""Independent watchdog: run with a systemd timer, never from run_monitoring."""

import os

import requests
from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, tenant_context

from monitoring.deliveries import BITRIX_CLIENT_FIELD, BITRIX_CLIENT_OPTION_ID, delivery_error_message
from monitoring.models import Monitor, WorkerHeartbeat
from monitoring.worker_health import worker_health


def _alert_emails():
    addresses = [part.strip() for part in os.getenv("MONITORING_WORKER_ALERT_EMAILS", "").split(",") if part.strip()]
    for address in addresses:
        try:
            validate_email(address)
        except ValidationError as exc:
            raise ValueError("MONITORING_WORKER_ALERT_EMAILS contiene un correo inválido") from exc
    return addresses


def _send_bitrix(schema, heartbeat):
    webhook = os.getenv("MONITORING_BITRIX_WEBHOOK_URL", "").rstrip("/")
    if not webhook.startswith("https://"):
        raise RuntimeError("Webhook Bitrix24 HTTPS no configurado")
    origin_id = f"worker:{schema}:{heartbeat.alert_opened_at.isoformat()}"
    found = requests.post(
        f"{webhook}/crm.item.list.json",
        json={"entityTypeId": 2, "filter": {"originatorId": "passing-monitoring", "originId": origin_id}, "select": ["id"]},
        timeout=5,
    )
    found.raise_for_status()
    body = found.json()
    if "error" in body:
        raise RuntimeError("Bitrix24 no pudo buscar negociaciones existentes")
    items = body.get("result", {}).get("items", [])
    if items:
        return str(items[0]["id"])
    created = requests.post(
        f"{webhook}/crm.item.add.json",
        json={"entityTypeId": 2, "useOriginalUfNames": "Y", "fields": {
            "title": f"[Monitorización] Worker sin actividad ({schema})",
            "categoryId": 174,
            "originatorId": "passing-monitoring",
            "originId": origin_id,
            BITRIX_CLIENT_FIELD: BITRIX_CLIENT_OPTION_ID,
            "comments": f"Tenant: {schema}\nÚltimo ciclo: {heartbeat.last_cycle_at or 'nunca'}\nDetectado: {heartbeat.alert_opened_at.isoformat()}",
        }},
        timeout=5,
    )
    created.raise_for_status()
    data = created.json()
    if "error" in data:
        raise RuntimeError("Bitrix24 rechazó la negociación")
    deal_id = data.get("result", {}).get("item", {}).get("id")
    if not deal_id:
        raise RuntimeError("Bitrix24 no devolvió el ID de negociación")
    return str(deal_id)


class Command(BaseCommand):
    help = "Detecta un worker detenido y avisa por correo y Bitrix24; ejecutar con un timer independiente."

    def handle(self, *args, **options):
        recipients = _alert_emails()
        bitrix_enabled = bool(os.getenv("MONITORING_BITRIX_WEBHOOK_URL", ""))
        unhealthy = 0
        for tenant in get_tenant_model().objects.exclude(schema_name="public"):
            with tenant_context(tenant):
                health = worker_health(list(Monitor.objects.filter(enabled=True)))
                if not health["active_count"]:
                    continue
                if health["worker_recent"] and not health["overdue_count"]:
                    WorkerHeartbeat.objects.filter(pk=1, alert_opened_at__isnull=False).update(
                        alert_opened_at=None, alert_email_sent_at=None, alert_bitrix_deal_id=""
                    )
                    continue
                unhealthy += 1
                with transaction.atomic():
                    heartbeat, _ = WorkerHeartbeat.objects.select_for_update().get_or_create(pk=1)
                    if not heartbeat.alert_opened_at:
                        heartbeat.alert_opened_at = timezone.now()
                        heartbeat.save(update_fields=["alert_opened_at"])
                reason = "worker sin actividad" if not health["worker_recent"] else f"{health['overdue_count']} checks atrasados"
                if recipients and not heartbeat.alert_email_sent_at:
                    try:
                        sent = send_mail(
                            f"[Monitorización] {reason} ({tenant.schema_name})",
                            f"Tenant: {tenant.schema_name}\nMotivo: {reason}\nÚltimo ciclo: {heartbeat.last_cycle_at or 'nunca'}\n",
                            settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False,
                            connection=get_connection(timeout=10),
                        )
                        if sent != 1:
                            raise RuntimeError("SMTP no aceptó la alerta")
                    except Exception as exc:
                        self.stderr.write(f"{tenant.schema_name}: correo: {delivery_error_message(exc, 'email')}")
                    else:
                        WorkerHeartbeat.objects.filter(pk=1, alert_email_sent_at__isnull=True).update(alert_email_sent_at=timezone.now())
                if bitrix_enabled and not heartbeat.alert_bitrix_deal_id:
                    try:
                        deal_id = _send_bitrix(tenant.schema_name, heartbeat)
                    except Exception as exc:
                        self.stderr.write(f"{tenant.schema_name}: Bitrix24: {delivery_error_message(exc, 'bitrix')}")
                    else:
                        WorkerHeartbeat.objects.filter(pk=1, alert_bitrix_deal_id="").update(alert_bitrix_deal_id=deal_id)
                self.stdout.write(f"{tenant.schema_name}: {reason}")
        if not unhealthy:
            self.stdout.write("Worker al día en todos los tenants activos")
