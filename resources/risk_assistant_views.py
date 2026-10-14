from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import RiskAssistantRun, RiskEvaluation, RiskInsight, Treatment
from .views import can_manage_resource
from supporthub.models import TelegramRecipient
from supporthub.services import SupportIntegrationError, _telegram_call
from supporthub.telegram_events import risk_assistant_message


@login_required
def dashboard(request):
    if not can_manage_resource(request.user, RiskEvaluation, 'view'):
        raise PermissionDenied
    status = request.GET.get('status', RiskInsight.Status.OPEN)
    if status not in RiskInsight.Status.values:
        status = RiskInsight.Status.OPEN
    insights = RiskInsight.objects.filter(status=status).select_related('evaluation').order_by(
        '-created_at', '-pk',
    )[:100]
    return render(request, 'risk_assistant_dashboard.html', {
        'insights': insights,
        'selected_status': status,
        'status_choices': RiskInsight.Status.choices,
        'open_count': RiskInsight.objects.filter(status=RiskInsight.Status.OPEN).count(),
        'latest_run': RiskAssistantRun.objects.first(),
        'can_review': can_manage_resource(request.user, RiskEvaluation, 'change'),
        'can_change_treatment': can_manage_resource(request.user, Treatment, 'change'),
        'can_test_telegram': TelegramRecipient.objects.filter(
            user=request.user, active=True, notify_risks=True,
        ).exists(),
    })


@login_required
@require_POST
def send_telegram_preview(request):
    if not can_manage_resource(request.user, RiskEvaluation, 'view'):
        raise PermissionDenied
    recipient = TelegramRecipient.objects.filter(
        user=request.user, active=True, notify_risks=True,
    ).first()
    if recipient is None:
        messages.warning(request, 'Activá la suscripción de riesgos en tu perfil de Telegram para recibir la prueba.')
        return redirect('risk-assistant')
    run = RiskAssistantRun.objects.filter(status='complete').first()
    if run is None or not run.digest_text.strip():
        messages.warning(request, 'Todavía no hay un resumen diario para enviar.')
        return redirect('risk-assistant')
    throttle_key = f'risk_telegram_preview:{connection.schema_name}:{request.user.pk}'
    if not cache.add(throttle_key, True, timeout=30):
        messages.info(request, 'Esperá unos segundos antes de enviar otra prueba.')
        return redirect('risk-assistant')
    try:
        _telegram_call('sendMessage', {
            'chat_id': recipient.chat_id, 'text': risk_assistant_message(run),
        })
    except SupportIntegrationError:
        cache.delete(throttle_key)
        messages.error(request, 'No se pudo enviar la prueba. Revisá el bot y tu chat en Configuración general.')
    else:
        messages.success(request, 'Envié el resumen a tu Telegram.')
    return redirect('risk-assistant')


@login_required
@require_POST
def update_insight(request, pk):
    if not can_manage_resource(request.user, RiskEvaluation, 'change'):
        raise PermissionDenied
    insight = get_object_or_404(RiskInsight, pk=pk, status__in=[RiskInsight.Status.OPEN, RiskInsight.Status.SNOOZED])
    action = request.POST.get('action')
    if action == 'review':
        insight.status = RiskInsight.Status.REVIEWED
        insight.reviewed_by = request.user
        insight.reviewed_at = timezone.now()
        insight.snoozed_until = None
    elif action == 'dismiss':
        insight.status = RiskInsight.Status.DISMISSED
        insight.reviewed_by = request.user
        insight.reviewed_at = timezone.now()
        insight.snoozed_until = None
    elif action == 'snooze':
        insight.status = RiskInsight.Status.SNOOZED
        insight.snoozed_until = timezone.localdate() + timedelta(days=7)
    else:
        messages.error(request, 'Acción no válida.')
        return redirect('risk-assistant')
    insight.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'snoozed_until', 'updated_at'])
    messages.success(request, 'Sugerencia actualizada.')
    return redirect('risk-assistant')
