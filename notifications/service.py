"""Registro mínimo de avisos para la campanita de Passing."""

from django.contrib.auth import get_user_model

from .models import InboxNotification


def record_inbox_notice(user, *, category, source_id, event, title, target_path='', channel=''):
    if not user or not user.is_active:
        return None
    if target_path and (not target_path.startswith('/') or target_path.startswith('//')):
        target_path = ''
    notice, created = InboxNotification.objects.get_or_create(
        user=user, category=category, source_id=source_id, event=event,
        defaults={'title': title[:120], 'target_path': target_path[:240], 'channels': channel},
    )
    if not created and channel and channel not in notice.channels.split(','):
        notice.channels = ','.join(sorted(filter(None, [*notice.channels.split(','), channel])))
        notice.save(update_fields=['channels'])
    return notice


def internal_users_for_emails(addresses):
    """Solo cuentas activas del tenant con la misma dirección que un destinatario."""
    normalized = {address.strip().casefold() for address in addresses if address.strip()}
    if not normalized:
        return []
    return [user for user in get_user_model().objects.filter(is_active=True).exclude(email='')
            if user.email.casefold() in normalized]
