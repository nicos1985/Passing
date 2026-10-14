"""Registro mínimo de avisos para la campanita de Passing."""

import logging
from django.contrib.auth import get_user_model

from .models import InboxNotification

logger = logging.getLogger(__name__)


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


def record_email_notice(addresses, *, category, source_id, event, title, target_path='', permissions=()):
    try:
        for user in internal_users_for_emails(addresses):
            can_open = not permissions or user.is_superuser or any(user.has_perm(permission) for permission in permissions)
            record_inbox_notice(
                user, category=category, source_id=source_id, event=event, title=title,
                target_path=target_path if can_open else '', channel='email',
            )
    except Exception:
        # Un problema en la campanita no debe provocar un segundo envío del correo.
        logger.exception('No se pudo registrar un aviso interno enviado por correo')
