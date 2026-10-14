from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BotTokenForm, ChatForm, PortalForm, RecipientForm, ShiftForm
from .models import BitrixPortal, DutyShift, SupportChat, SupportNotice, TelegramBotConfig, TelegramDelivery, TelegramPairing, TelegramRecipient
from .services import SupportIntegrationError, _telegram_call, list_private_telegram_chats


ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')


def _can_view(user):
    return user.is_active and (user.is_superuser or user.has_perm('supporthub.view_support_inbox'))


def _can_manage(user, action='edit'):
    return user.is_active and (
        user.is_superuser or user.has_perm(f'supporthub.{action}_support')
    )


@login_required
def inbox(request):
    if not _can_view(request.user):
        return HttpResponseForbidden()
    state = request.GET.get('state', 'all')
    notices = SupportNotice.objects.select_related('chat__portal').order_by('-last_at', '-pk')
    if state in {'pending', 'sent', 'failed'}:
        notices = notices.filter(status=state)
    else:
        state = 'all'
    requested_size = request.GET.get('per_page', '10')
    per_page = int(requested_size) if requested_size in {'10', '25', '50'} else 10
    paginator = Paginator(notices, per_page)
    page = paginator.get_page(request.GET.get('page'))
    active_shift = DutyShift.objects.select_related('primary__user', 'backup__user').filter(
        starts_at__lte=timezone.now(), ends_at__gt=timezone.now(),
    ).order_by('-starts_at').first()
    return render(request, 'supporthub/inbox.html', {
        'page': page, 'state': state, 'per_page': per_page,
        'page_numbers': paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1),
        'pagination_ellipsis': paginator.ELLIPSIS, 'active_shift': active_shift,
        'pending_count': SupportNotice.objects.filter(status='pending').count(),
        'failed_count': SupportNotice.objects.filter(status='failed').count(),
        'portals': BitrixPortal.objects.prefetch_related('chats').all(),
        'is_manager': any(_can_manage(request.user, action) for action in ('create', 'edit', 'delete')),
        'can_retry': _can_manage(request.user, 'edit'), 'argentina': ARGENTINA,
    })


@login_required
def settings_page(request):
    if not any(_can_manage(request.user, action) for action in ('create', 'edit', 'delete')):
        return HttpResponseForbidden()
    context = _settings_context()
    context.update({f'can_{action}': _can_manage(request.user, action) for action in ('create', 'edit', 'delete')})
    return render(request, 'supporthub/settings.html', context)


def _settings_context():
    return {
        'portals': BitrixPortal.objects.prefetch_related('chats').all(),
        'shifts': DutyShift.objects.select_related('primary__user', 'backup__user').order_by('-starts_at')[:50],
        'now': timezone.now(),
    }


def _form_view(request, *, model, form_class, pk, title, return_url='supporthub:settings'):
    if not _can_manage(request.user, 'edit' if pk else 'create'):
        return HttpResponseForbidden()
    instance = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Configuración guardada.')
        return redirect(return_url)
    return render(request, 'supporthub/form.html', {'form': form, 'title': title, 'return_url': return_url})


@login_required
def portal_form(request, pk=None):
    return _form_view(request, model=BitrixPortal, form_class=PortalForm, pk=pk, title='Portal Bitrix24')


@login_required
def chat_form(request, pk=None):
    return _form_view(request, model=SupportChat, form_class=ChatForm, pk=pk, title='Grupo de soporte')


@login_required
def recipient_form(request, pk=None):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    return _form_view(request, model=TelegramRecipient, form_class=RecipientForm, pk=pk,
                      title='Cuenta de Telegram', return_url='notification_settings')


@login_required
def shift_form(request, pk=None):
    return _form_view(request, model=DutyShift, form_class=ShiftForm, pk=pk, title='Turno de guardia · hora de Argentina')


@login_required
def bot_form(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('notification_settings')
    form = BotTokenForm(request.POST)
    if request.method == 'POST' and form.is_valid():
        config, _ = TelegramBotConfig.objects.get_or_create(pk=1)
        config.set_token(form.cleaned_data['token'])
        config.save()
        messages.success(request, 'Token del bot guardado de forma cifrada. Probá la conexión antes de usarlo.')
        return redirect('notification_settings')
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)
    return redirect('notification_settings')


@login_required
@require_POST
def bot_test(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    try:
        bot = _telegram_call('getMe')
        if not isinstance(bot, dict) or not bot.get('is_bot'):
            raise SupportIntegrationError('Telegram no confirmó la identidad del bot.')
    except SupportIntegrationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Conexión con el bot confirmada por Telegram.')
    return redirect('notification_settings')


@login_required
@require_POST
def discover_telegram_chats(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    try:
        chats = list_private_telegram_chats()
    except SupportIntegrationError as exc:
        messages.error(request, str(exc))
        return redirect('notification_settings')
    request.session['telegram_discovered_chats'] = chats
    return redirect('notification_settings')


@login_required
@require_POST
def retry_notice(request, pk):
    if not _can_manage(request.user, 'edit'):
        return HttpResponseForbidden()
    notice = get_object_or_404(SupportNotice, pk=pk)
    notice.status = SupportNotice.Status.PENDING
    notice.notify_after = timezone.now()
    notice.last_error = ''
    notice.save(update_fields=['status', 'notify_after', 'last_error'])
    TelegramDelivery.objects.filter(notice=notice, status=SupportNotice.Status.FAILED).update(
        status=SupportNotice.Status.PENDING, attempts=0, next_attempt_at=timezone.now(), last_error='',
    )
    messages.success(request, 'El aviso se reintentará en el próximo ciclo.')
    return redirect('supporthub:inbox')


@login_required
@require_POST
def test_recipient(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    recipient = get_object_or_404(TelegramRecipient, pk=pk)
    try:
        _telegram_call('sendMessage', {
            'chat_id': recipient.chat_id, 'text': 'Passing · prueba de avisos de soporte',
        })
    except SupportIntegrationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Telegram recibió el aviso de prueba.')
    return redirect('notification_settings')


@login_required
def delete_item(request, kind, pk):
    if not _can_manage(request.user, 'delete'):
        return HttpResponseForbidden()
    choices = {
        'portal': (BitrixPortal, 'portal Bitrix24', 'supporthub:settings'),
        'chat': (SupportChat, 'grupo de chat', 'supporthub:settings'),
        'recipient': (TelegramRecipient, 'cuenta de Telegram', 'notification_settings'),
        'shift': (DutyShift, 'turno de guardia', 'supporthub:settings'),
    }
    if kind not in choices:
        return HttpResponseForbidden()
    if kind == 'recipient' and not request.user.is_superuser:
        return HttpResponseForbidden()
    model, label, return_url = choices[kind]
    item = get_object_or_404(model, pk=pk)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if kind == 'recipient':
                    item = get_object_or_404(TelegramRecipient.objects.select_for_update(), pk=pk)
                    if DutyShift.objects.filter(primary=item).exists() or DutyShift.objects.filter(backup=item).exists():
                        messages.error(request, 'Esta cuenta figura en turnos de guardia. Borrá primero esos turnos.')
                        return redirect(return_url)
                    TelegramDelivery.objects.filter(recipient=item).delete()
                    TelegramPairing.objects.filter(user=item.user).delete()
                item.delete()
        except ProtectedError:
            messages.error(request, 'Hay registros vinculados. Borrá primero esas dependencias.')
        else:
            messages.success(request, f'Se eliminó el {label}.')
        return redirect(return_url)
    return render(request, 'supporthub/confirm_delete.html', {
        'item': item, 'kind': kind, 'label': label, 'return_url': return_url,
        'related_count': item.chats.count() if kind == 'portal' else (item.notices.count() if kind == 'chat' else 0),
        'has_shifts': kind == 'recipient' and (
            DutyShift.objects.filter(primary=item).exists() or DutyShift.objects.filter(backup=item).exists()
        ),
    })
