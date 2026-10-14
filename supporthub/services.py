"""Lectura de eventos Bitrix24 y entrega de avisos mínimos a Telegram."""

import ipaddress
import json
import os
import socket
import ssl
from datetime import timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BitrixPortal, DutyShift, SupportChat, SupportMessage, SupportNotice, TelegramBotConfig, TelegramDelivery, TelegramRecipient
from notifications.service import record_inbox_notice
from django.urls import reverse


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')


class SupportIntegrationError(Exception):
    """Mensaje seguro para mostrar en consola sin filtrar secretos externos."""


class SystemTrustAdapter(HTTPAdapter):
    """Verifica HTTPS con las autoridades confiables del sistema operativo."""

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = ssl.create_default_context()
        return super().init_poolmanager(*args, **kwargs)


def _public_host(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SupportIntegrationError('No se pudo resolver el dominio del portal.') from exc
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise SupportIntegrationError('El portal debe resolver a direcciones públicas.')


def _post_json(url, data, *, is_bitrix=False):
    if is_bitrix:
        _public_host(urlsplit(url).hostname)
    session = requests.Session()
    session.trust_env = False
    session.mount('https://', SystemTrustAdapter())
    try:
        with session.post(url, json=data, timeout=(3, 10), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                if is_bitrix:
                    raise SupportIntegrationError(f'Bitrix24 respondió HTTP {response.status_code}.')
                if response.status_code in (400, 403):
                    raise SupportIntegrationError('Telegram rechazó el destinatario; verificá /start y el chat ID.')
                raise SupportIntegrationError(f'Telegram respondió HTTP {response.status_code}.')
            content = bytearray()
            for part in response.iter_content(chunk_size=16384):
                content.extend(part)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise SupportIntegrationError('La respuesta externa superó el límite permitido.')
            try:
                return json.loads(content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SupportIntegrationError('La respuesta externa no es JSON válido.') from exc
    except requests.RequestException as exc:
        service = 'Bitrix24' if is_bitrix else 'Telegram'
        raise SupportIntegrationError(f'No se pudo conectar con {service} ({type(exc).__name__}).') from exc
    finally:
        session.close()


def _bitrix_call(portal, method, payload=None):
    data = _post_json(portal.webhook_url() + method, payload or {}, is_bitrix=True)
    if not isinstance(data, dict) or data.get('error'):
        code = data.get('error', '') if isinstance(data, dict) else ''
        if code in {'ACCESS_DENIED', 'insufficient_scope', 'ERROR_METHOD_NOT_FOUND'}:
            raise SupportIntegrationError('Bitrix24 no permite leer eventos; comprobá plan y permiso im.')
        raise SupportIntegrationError('Bitrix24 rechazó la consulta de eventos.')
    return data.get('result')


def _event_time(raw):
    parsed = parse_datetime(raw or '')
    return parsed if parsed and timezone.is_aware(parsed) else timezone.now()


def _record_event(portal, event, chats, now):
    if event.get('type') != 'ONIMV2MESSAGEADD':
        return False
    data = event.get('data') or {}
    if not isinstance(data, dict):
        return False
    message = data.get('message') or {}
    chat_data = data.get('chat') or {}
    user_data = data.get('user') or {}
    if not all(isinstance(item, dict) for item in (message, chat_data, user_data)):
        return False
    chat = chats.get(str(chat_data.get('dialogId', '')))
    if not chat or message.get('isSystem') or user_data.get('bot'):
        return False
    try:
        message_id = int(message['id'])
        author_id = int(message['authorId'])
        own_id = int(urlsplit(portal.webhook_url()).path.split('/')[2])
    except (KeyError, ValueError, TypeError, IndexError):
        return False
    if message_id <= 0 or author_id <= 0 or author_id == own_id or author_id in chat.ignored_ids:
        return False
    if SupportMessage.objects.filter(portal=portal, message_id=message_id).exists():
        return False
    notice = SupportNotice.objects.filter(
        chat=chat, status=SupportNotice.Status.PENDING, notify_after__gt=now,
    ).order_by('-last_at').first()
    occurred = _event_time(message.get('date') or event.get('date'))
    if notice:
        notice.last_at = max(notice.last_at, occurred)
        notice.message_count += 1
        notice.save(update_fields=['last_at', 'message_count'])
    else:
        notice = SupportNotice.objects.create(
            chat=chat, first_at=occurred, last_at=occurred,
            notify_after=now + timedelta(seconds=60),
        )
    SupportMessage.objects.create(
        portal=portal, chat=chat, notice=notice, message_id=message_id,
        author_id=author_id, occurred_at=occurred,
    )
    return True


def poll_portal(portal, *, max_batches=10):
    if not portal.enabled or not portal.webhook_encrypted:
        return 0
    try:
        if portal.subscribed_at is None:
            if _bitrix_call(portal, 'im.v2.Event.subscribe') is not True:
                raise SupportIntegrationError('Bitrix24 no confirmó la suscripción a eventos.')
            portal.subscribed_at = timezone.now()
            portal.save(update_fields=['subscribed_at'])
        chats = {chat.dialog_id: chat for chat in portal.chats.filter(enabled=True)}
        count = 0
        for _ in range(max_batches):
            params = {'limit': 100}
            if portal.next_offset is not None:
                params['offset'] = portal.next_offset
            result = _bitrix_call(portal, 'im.v2.Event.get', params)
            if not isinstance(result, dict) or not isinstance(result.get('events'), list):
                raise SupportIntegrationError('Bitrix24 devolvió eventos con formato inesperado.')
            next_offset = result.get('nextOffset')
            if type(next_offset) is not int or next_offset < 0:
                raise SupportIntegrationError('Bitrix24 no devolvió un cursor válido.')
            now = timezone.now()
            with transaction.atomic():
                for event in result['events']:
                    if isinstance(event, dict) and _record_event(portal, event, chats, now):
                        count += 1
                portal.next_offset = next_offset
                portal.last_polled_at = now
                portal.last_error = ''
                portal.save(update_fields=['next_offset', 'last_polled_at', 'last_error'])
            if not result.get('hasMore'):
                break
        return count
    except (SupportIntegrationError, ValueError) as exc:
        portal.last_error = (str(exc) if isinstance(exc, SupportIntegrationError) else 'El webhook configurado no se pudo leer.')[:200]
        portal.save(update_fields=['last_error'])
        return 0


def _recipients_for_notice(notice, now):
    shift = DutyShift.objects.select_related('primary__user', 'backup__user').filter(
        starts_at__lte=now, ends_at__gt=now,
    ).order_by('-starts_at').first()
    if shift:
        backup = shift.backup
        backup = backup if backup and backup.active and backup.notify_support and backup.user.is_active else None
        if shift.primary.active and shift.primary.notify_support and shift.primary.user.is_active:
            return [shift.primary], backup
        if backup:
            return [backup], None
    return list(TelegramRecipient.objects.filter(active=True, fallback=True, notify_support=True, user__is_active=True).select_related('user')), None


def get_telegram_token():
    config = TelegramBotConfig.objects.filter(pk=1).first()
    if config and config.token_encrypted:
        try:
            return config.token()
        except ValueError as exc:
            raise SupportIntegrationError('No se pudo leer el token de Telegram guardado en Passing.') from exc
    token = os.getenv('SUPPORT_TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        raise SupportIntegrationError('Configurá el bot de Telegram en Passing.')
    return token


def _telegram_call(method, payload=None):
    result = _post_json(f'https://api.telegram.org/bot{get_telegram_token()}/{method}', payload or {})
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise SupportIntegrationError('Telegram rechazó la solicitud. Revisá el token del bot.')
    return result.get('result')


def list_private_telegram_chats():
    """Devuelve IDs y nombres recientes; no conserva ni muestra los mensajes."""
    updates = _telegram_call('getUpdates', {'limit': 100})
    if not isinstance(updates, list):
        raise SupportIntegrationError('Telegram devolvió una respuesta inesperada.')
    chats = {}
    for update in updates:
        if not isinstance(update, dict):
            continue
        message = update.get('message') or {}
        if not isinstance(message, dict):
            continue
        chat = message.get('chat') or {}
        if not isinstance(chat, dict) or chat.get('type') != 'private':
            continue
        chat_id = chat.get('id')
        if type(chat_id) is not int or chat_id <= 0:
            continue
        name = ' '.join(str(chat.get(part) or '').strip() for part in ('first_name', 'last_name')).strip()
        username = str(chat.get('username') or '').strip()
        chats[chat_id] = {'id': chat_id, 'name': name[:100], 'username': username[:100]}
    return [chats[chat_id] for chat_id in sorted(chats)]


def _send_telegram(delivery):
    notice = delivery.notice
    chat = notice.chat
    moment = notice.last_at.astimezone(ARGENTINA).strftime('%d/%m %H:%M')
    count = 'un mensaje nuevo' if notice.message_count == 1 else f'{notice.message_count} mensajes nuevos'
    content = f'Soporte · {chat.portal.name}\n{chat.label}: {count}\n{moment} (Argentina)\nAbrir en Bitrix24: {chat.open_url}'
    _telegram_call('sendMessage', {
        'chat_id': delivery.recipient.chat_id, 'text': content,
    })


def dispatch_notices(limit=50):
    now = timezone.now()
    due = SupportNotice.objects.select_related('chat__portal').filter(
        Q(status=SupportNotice.Status.PENDING, notify_after__lte=now)
        | Q(deliveries__status=SupportNotice.Status.PENDING, deliveries__next_attempt_at__lte=now)
    ).distinct().order_by('notify_after')[:limit]
    for notice in due:
        if not notice.deliveries.exists():
            recipients, _backup = _recipients_for_notice(notice, now)
            if not recipients:
                notice.last_error = 'No hay guardia activa ni destinatario de respaldo.'
                notice.notify_after = now + timedelta(minutes=5)
                notice.save(update_fields=['last_error', 'notify_after'])
                continue
            for recipient in recipients:
                TelegramDelivery.objects.get_or_create(
                    notice=notice, recipient=recipient, defaults={'next_attempt_at': now},
                )
        for delivery in notice.deliveries.select_related('recipient').filter(
            status=SupportNotice.Status.PENDING, next_attempt_at__lte=now,
        ):
            if not delivery.recipient.active or not delivery.recipient.notify_support or not delivery.recipient.user.is_active:
                delivery.status = SupportNotice.Status.FAILED
                delivery.last_error = 'El destinatario desactivó los avisos de soporte.'
                delivery.save(update_fields=['status', 'last_error'])
                continue
            user = delivery.recipient.user
            record_inbox_notice(
                user, category='support', source_id=notice.pk, event='message',
                title='Nuevo aviso de soporte',
                target_path=(reverse('supporthub:inbox', urlconf='passing.urls_tenant')
                             if user.is_superuser or user.has_perm('supporthub.view_support_inbox') else ''),
                channel='telegram',
            )
            try:
                _send_telegram(delivery)
            except SupportIntegrationError as exc:
                delivery.attempts += 1
                delivery.last_error = str(exc)[:200]
                if delivery.attempts >= 5:
                    delivery.status = SupportNotice.Status.FAILED
                else:
                    delivery.next_attempt_at = now + timedelta(seconds=min(300, 30 * 2 ** (delivery.attempts - 1)))
                delivery.save(update_fields=['attempts', 'last_error', 'status', 'next_attempt_at'])
                # Si falla el principal, también avisar al suplente configurado en este turno.
                _, backup = _recipients_for_notice(notice, now)
                if backup and backup.pk != delivery.recipient_id:
                    TelegramDelivery.objects.get_or_create(
                        notice=notice, recipient=backup, defaults={'next_attempt_at': now},
                    )
            else:
                delivery.attempts += 1
                delivery.status = SupportNotice.Status.SENT
                delivery.sent_at = timezone.now()
                delivery.last_error = ''
                delivery.save(update_fields=['attempts', 'status', 'sent_at', 'last_error'])
        if notice.deliveries.filter(status=SupportNotice.Status.SENT).exists():
            notice.status = SupportNotice.Status.SENT
            notice.sent_at = timezone.now()
            notice.last_error = ''
        elif not notice.deliveries.filter(status=SupportNotice.Status.PENDING).exists():
            notice.status = SupportNotice.Status.FAILED
            notice.last_error = 'No se pudo entregar por Telegram.'
        notice.save(update_fields=['status', 'sent_at', 'last_error'])


def purge_old_history(days=90):
    SupportNotice.objects.filter(last_at__lt=timezone.now() - timedelta(days=days)).delete()
    from .models import TelegramEventDelivery, TelegramPairing
    from notifications.models import InboxNotification
    TelegramEventDelivery.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
    TelegramPairing.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
    InboxNotification.objects.filter(created_at__lt=timezone.now() - timedelta(days=365)).delete()
