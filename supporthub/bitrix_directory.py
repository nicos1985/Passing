"""Transient chat and user discovery using the stored incoming webhook.

Only IDs, display names and public messenger links leave this module. Message
bodies, avatars, phone numbers and email addresses are never returned or saved.
"""

import re
from django.utils.dateparse import parse_datetime

from .links import group_url
from .services import SupportIntegrationError, _bitrix_call

PAGE_SIZE = 50


def _items(result):
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        if isinstance(result.get('items'), list):
            return result['items']
        if all(isinstance(item, dict) for item in result.values()):
            return list(result.values())
    raise SupportIntegrationError('Bitrix24 devolvió un listado inesperado.')


def _positive_id(value):
    value = str(value)
    return value if re.fullmatch(r'[1-9][0-9]{0,17}', value) else None


def list_groups(portal, *, query='', offset=0, cursor=None):
    if query:
        result = _bitrix_call(portal, 'im.search.chat.list', {'FIND': query, 'OFFSET': offset, 'LIMIT': PAGE_SIZE})
    else:
        params = {'SKIP_DIALOG': 'Y', 'SKIP_OPENLINES': 'Y', 'LIMIT': PAGE_SIZE}
        if cursor:
            params['LAST_MESSAGE_DATE'] = cursor
        result = _bitrix_call(portal, 'im.recent.list', params)
    rows = _items(result)
    groups = {}
    for row in rows[:PAGE_SIZE]:
        if not isinstance(row, dict) or row.get('type') == 'user':
            continue
        dialog = str(row.get('id', ''))
        if query:
            number = _positive_id(dialog)
            dialog = f'chat{number}' if number else dialog
        if not re.fullmatch(r'chat[1-9][0-9]{0,17}', dialog):
            continue
        name = row.get('title') or row.get('name') or f'Grupo {dialog}'
        groups[dialog] = {'id': dialog, 'name': str(name)[:100], 'link': group_url(portal.base_url, dialog)}
    next_cursor = None
    if not query and isinstance(result, dict) and (result.get('hasMore') or result.get('hasMorePages')) and rows:
        # Recent-chat pagination uses a timestamp, not an integer offset.
        last = rows[min(len(rows), PAGE_SIZE) - 1]
        message = last.get('message') if isinstance(last, dict) else None
        raw = message.get('date') if isinstance(message, dict) else None
        parsed = parse_datetime(raw) if isinstance(raw, str) else None
        if parsed and parsed.utcoffset() is not None and (not cursor or parsed != parse_datetime(cursor)):
            next_cursor = parsed.isoformat()
    return {'items': list(groups.values()), 'next_offset': offset + PAGE_SIZE if query and len(rows) >= PAGE_SIZE and offset < 10000 else None,
            'next_cursor': next_cursor}


def list_people(portal, *, query='', dialog='', offset=0):
    if query:
        result = _bitrix_call(portal, 'im.search.user.list', {'FIND': query, 'OFFSET': offset, 'LIMIT': PAGE_SIZE})
    else:
        result = _bitrix_call(portal, 'im.dialog.users.list', {
            'DIALOG_ID': dialog, 'SKIP_EXTERNAL': 'Y', 'OFFSET': offset, 'LIMIT': PAGE_SIZE,
        })
    rows = _items(result)
    people = {}
    for row in rows[:PAGE_SIZE]:
        if not isinstance(row, dict) or row.get('bot') or row.get('connector'):
            continue
        identifier = _positive_id(row.get('id'))
        if not identifier:
            continue
        name = row.get('name') or ' '.join(str(row.get(key) or '') for key in ('first_name', 'last_name')).strip()
        people[identifier] = {'id': identifier, 'name': str(name or f'Usuario {identifier}')[:100]}
    return {'items': list(people.values()), 'next_offset': offset + PAGE_SIZE if len(rows) >= PAGE_SIZE and offset < 10000 else None}
