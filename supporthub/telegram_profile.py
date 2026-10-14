"""Vinculación verificada de un chat privado al perfil."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SupportNotice, TelegramDelivery, TelegramEventDelivery, TelegramPairing, TelegramRecipient
from .services import SupportIntegrationError, _telegram_call


def _page(request):
    recipient = TelegramRecipient.objects.filter(user=request.user).first()
    pairing = TelegramPairing.objects.filter(user=request.user, expires_at__gt=timezone.now()).first()
    can_monitor = request.user.is_superuser or request.user.has_perm('monitoring.manage_monitoring') or request.user.has_perm('monitoring.read_monitoring')
    can_risks = request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_riskevaluation')
    can_password = request.user.is_superuser
    return render(request, 'supporthub/telegram_profile.html', {
        'recipient': recipient, 'pairing': pairing,
        'can_monitor': can_monitor, 'can_password': can_password, 'can_risks': can_risks,
    })


@login_required
def telegram_profile(request):
    return _page(request)


@login_required
@require_POST
def start_pairing(request):
    raw = request.POST.get('chat_id', '').strip()
    if not raw.isascii() or not raw.isdigit() or len(raw) > 19 or not 0 < int(raw) < 2 ** 63:
        messages.error(request, 'Ingresá un ID numérico de chat privado válido.')
        return redirect('supporthub:telegram_profile')
    chat_id = int(raw)
    if TelegramRecipient.objects.filter(chat_id=chat_id, user=request.user).exists():
        messages.info(request, 'Ese chat ya es tuyo. Administrá las suscripciones más abajo.')
        return redirect('supporthub:telegram_profile')
    if TelegramRecipient.objects.filter(user=request.user).exists() and TelegramRecipient.objects.filter(chat_id=chat_id).exclude(user=request.user).exists():
        messages.error(request, 'Tu perfil ya tiene otro chat. Pedile al administrador que quite esa cuenta antes de transferir este chat.')
        return redirect('supporthub:telegram_profile')
    existing = TelegramPairing.objects.filter(user=request.user).first()
    if existing and existing.expires_at > timezone.now() + timedelta(minutes=9):
        messages.warning(request, 'Esperá un minuto antes de solicitar otro código.')
        return redirect('supporthub:telegram_profile')
    code = f'{secrets.randbelow(100000000):08d}'
    try:
        _telegram_call('sendMessage', {'chat_id': chat_id, 'text': f'Código de vinculación de Passing: {code}\nVence en 10 minutos.'})
    except SupportIntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('supporthub:telegram_profile')
    TelegramPairing.objects.update_or_create(user=request.user, defaults={
        'pending_chat_id': chat_id, 'code_hash': hashlib.sha256(code.encode()).hexdigest(),
        'expires_at': timezone.now() + timedelta(minutes=10), 'attempts': 0,
    })
    messages.success(request, 'Te enviamos un código por Telegram. Ingresalo para confirmar el chat.')
    return redirect('supporthub:telegram_profile')


@login_required
@require_POST
def confirm_pairing(request):
    pairing = TelegramPairing.objects.filter(user=request.user).first()
    code = request.POST.get('code', '').strip()
    if not pairing or pairing.expires_at <= timezone.now() or pairing.attempts >= 5:
        messages.error(request, 'El código venció. Solicitá uno nuevo.')
        return redirect('supporthub:telegram_profile')
    pairing.attempts += 1
    pairing.save(update_fields=['attempts'])
    if not code.isascii() or not code.isdigit() or len(code) != 8 or not hmac.compare_digest(
        pairing.code_hash, hashlib.sha256(code.encode()).hexdigest(),
    ):
        messages.error(request, 'Código incorrecto.')
        return redirect('supporthub:telegram_profile')
    with transaction.atomic():
        existing = TelegramRecipient.objects.select_for_update().filter(chat_id=pairing.pending_chat_id).first()
        own = TelegramRecipient.objects.select_for_update().filter(user=request.user).first()
        if existing and existing.user_id != request.user.pk:
            if own:
                messages.error(request, 'Tu perfil ya tiene otro chat. Pedile al administrador que quite esa cuenta antes de transferir este chat.')
                return redirect('supporthub:telegram_profile')
            # El código recibido en el chat acredita posesión. La cuenta conserva sus
            # turnos históricos, pero se desactivan las preferencias del dueño previo.
            TelegramEventDelivery.objects.filter(
                recipient=existing, status=TelegramEventDelivery.Status.PENDING,
            ).update(status=TelegramEventDelivery.Status.CANCELLED)
            TelegramDelivery.objects.filter(
                recipient=existing, status=SupportNotice.Status.PENDING,
            ).update(status=SupportNotice.Status.FAILED, last_error='Chat reasignado a otra cuenta.')
            existing.user = request.user
            existing.active = True
            existing.fallback = False
            existing.notify_support = False
            existing.notify_monitoring = False
            existing.notify_password_requests = False
            existing.notify_risks = False
            existing.save(update_fields=[
                'user', 'active', 'fallback', 'notify_support', 'notify_monitoring', 'notify_password_requests', 'notify_risks',
            ])
            transferred = True
        else:
            recipient, created = TelegramRecipient.objects.get_or_create(user=request.user, defaults={
                'chat_id': pairing.pending_chat_id, 'active': True, 'notify_support': False,
            })
            if not created:
                recipient.chat_id = pairing.pending_chat_id
                recipient.active = True
                recipient.save(update_fields=['chat_id', 'active'])
            transferred = False
        pairing.delete()
    if transferred:
        messages.success(request, 'Chat recuperado para tu perfil. Los avisos de la cuenta anterior se desactivaron; elegí abajo tus suscripciones.')
    else:
        messages.success(request, 'Chat de Telegram vinculado. Elegí ahora qué avisos querés recibir.')
    return redirect('supporthub:telegram_profile')


@login_required
@require_POST
def save_preferences(request):
    recipient = TelegramRecipient.objects.filter(user=request.user).first()
    if not recipient:
        messages.error(request, 'Primero vinculá tu chat de Telegram.')
        return redirect('supporthub:telegram_profile')
    recipient.active = 'active' in request.POST
    recipient.notify_support = 'notify_support' in request.POST
    recipient.notify_monitoring = ('notify_monitoring' in request.POST and (
        request.user.is_superuser or request.user.has_perm('monitoring.manage_monitoring') or request.user.has_perm('monitoring.read_monitoring')
    ))
    recipient.notify_password_requests = 'notify_password_requests' in request.POST and request.user.is_superuser
    recipient.notify_risks = 'notify_risks' in request.POST and (
        request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_riskevaluation')
    )
    recipient.save(update_fields=['active', 'notify_support', 'notify_monitoring', 'notify_password_requests', 'notify_risks'])
    messages.success(request, 'Preferencias de Telegram guardadas.')
    return redirect('supporthub:telegram_profile')


@login_required
@require_POST
def unlink_chat(request):
    TelegramPairing.objects.filter(user=request.user).delete()
    recipient = TelegramRecipient.objects.filter(user=request.user).first()
    if recipient:
        # Los turnos históricos protegen el destinatario; se desactiva sin borrarlo.
        recipient.active = False
        recipient.notify_support = False
        recipient.notify_monitoring = False
        recipient.notify_password_requests = False
        recipient.notify_risks = False
        recipient.save(update_fields=['active', 'notify_support', 'notify_monitoring', 'notify_password_requests', 'notify_risks'])
    messages.success(request, 'Los avisos de Telegram quedaron desactivados.')
    return redirect('supporthub:telegram_profile')
