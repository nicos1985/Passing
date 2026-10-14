"""Cola mínima de avisos Telegram ajenos a la bandeja de soporte."""

from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from notifications.service import record_inbox_notice

from .models import TelegramEventDelivery, TelegramRecipient
from .services import SupportIntegrationError, _telegram_call


def _eligible(recipient, category):
    user = recipient.user
    if not recipient.active or not user.is_active:
        return False
    if category == TelegramEventDelivery.Category.MONITORING:
        return recipient.notify_monitoring and (user.is_superuser or user.has_perm('monitoring.manage_monitoring') or user.has_perm('monitoring.read_monitoring'))
    if category == TelegramEventDelivery.Category.PASSWORD_REQUEST:
        return recipient.notify_password_requests and user.is_superuser
    if category == TelegramEventDelivery.Category.RISK_ASSISTANT:
        return recipient.notify_risks and (user.is_staff or user.is_superuser or user.has_perm('resources.view_riskevaluation'))
    return False


def _queue(category, source_id, event):
    for recipient in TelegramRecipient.objects.filter(active=True, user__is_active=True).select_related('user'):
        if _eligible(recipient, category):
            TelegramEventDelivery.objects.get_or_create(
                recipient=recipient, category=category, source_id=source_id, event=event,
            )
            if category == TelegramEventDelivery.Category.MONITORING:
                record_inbox_notice(
                    recipient.user, category='monitoring', source_id=source_id, event=event,
                    title='Incidente de monitorización' if event == 'opened' else 'Servicio recuperado',
                    target_path=reverse('monitoring:incident', args=[source_id], urlconf='passing.urls_tenant'),
                    channel='telegram',
                )
            elif category == TelegramEventDelivery.Category.RISK_ASSISTANT:
                record_inbox_notice(
                    recipient.user, category='risks', source_id=source_id, event=event,
                    title='Nuevo resumen de riesgos',
                    target_path=reverse('risk-assistant', urlconf='passing.urls_tenant'),
                    channel='telegram',
                )


def queue_monitoring_event(incident_id, event):
    _queue(TelegramEventDelivery.Category.MONITORING, incident_id, event)


def queue_password_request(notification_id):
    _queue(TelegramEventDelivery.Category.PASSWORD_REQUEST, notification_id, 'opened')


def queue_risk_assistant_digest(run_id):
    _queue(TelegramEventDelivery.Category.RISK_ASSISTANT, run_id, 'daily')


def _absolute_url(path):
    domain = connection.tenant.get_primary_domain()
    if not domain:
        raise SupportIntegrationError('El tenant no tiene dominio principal.')
    return f'{settings.TENANT_SCHEME}://{domain.domain}{path}'


def risk_assistant_message(run):
    body = run.digest_text.strip() or f'Buen día 👋 Hay {run.created_count} sugerencias de riesgos para revisar.'
    return f'{body}\n\nVer el detalle en Passing: {_absolute_url(reverse("risk-assistant", urlconf="passing.urls_tenant"))}'


def _message(delivery):
    if delivery.category == TelegramEventDelivery.Category.RISK_ASSISTANT:
        from resources.models import RiskAssistantRun
        run = RiskAssistantRun.objects.filter(pk=delivery.source_id, status='complete').first()
        if not run:
            return None
        return risk_assistant_message(run)
    if delivery.category == TelegramEventDelivery.Category.MONITORING:
        from monitoring.models import Incident
        incident = Incident.objects.select_related('monitor').filter(pk=delivery.source_id).first()
        if not incident:
            return None
        label = 'Incidente detectado' if delivery.event == 'opened' else 'Servicio recuperado'
        return f'{label}: {incident.monitor.name}\nAbrir en Passing: {_absolute_url(reverse("monitoring:incident", args=[incident.pk], urlconf="passing.urls_tenant"))}'
    if delivery.category == TelegramEventDelivery.Category.PASSWORD_REQUEST:
        from notifications.models import AdminNotification
        if not AdminNotification.objects.filter(pk=delivery.source_id).exists():
            return None
        return f'Nueva solicitud de acceso a contraseña\nAbrir en Passing: {_absolute_url(reverse("listnotifadmin", urlconf="passing.urls_tenant"))}'
    return None


def dispatch_event_deliveries(limit=50):
    now = timezone.now()
    deliveries = TelegramEventDelivery.objects.select_related('recipient__user').filter(
        status=TelegramEventDelivery.Status.PENDING, next_attempt_at__lte=now,
    ).order_by('created_at')[:limit]
    for delivery in deliveries:
        if not _eligible(delivery.recipient, delivery.category):
            delivery.status = TelegramEventDelivery.Status.CANCELLED
            delivery.save(update_fields=['status'])
            continue
        try:
            message = _message(delivery)
            if message is None:
                delivery.status = TelegramEventDelivery.Status.CANCELLED
                delivery.save(update_fields=['status'])
                continue
            _telegram_call('sendMessage', {'chat_id': delivery.recipient.chat_id, 'text': message})
        except SupportIntegrationError as exc:
            delivery.attempts += 1
            delivery.last_error = str(exc)[:200]
            if delivery.attempts >= 5:
                delivery.status = TelegramEventDelivery.Status.FAILED
            else:
                delivery.next_attempt_at = now + timedelta(seconds=min(300, 30 * 2 ** (delivery.attempts - 1)))
            delivery.save(update_fields=['attempts', 'last_error', 'status', 'next_attempt_at'])
        else:
            delivery.attempts += 1
            delivery.status = TelegramEventDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.last_error = ''
            delivery.save(update_fields=['attempts', 'status', 'sent_at', 'last_error'])
