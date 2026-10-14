"""Muestra únicamente los IDs de chats que iniciaron el bot; omite contenido."""

import os

from django.core.management.base import BaseCommand, CommandError

from supporthub.services import SupportIntegrationError, _post_json


class Command(BaseCommand):
    help = 'Consulta IDs de chats recientes de Telegram para vincular destinatarios.'

    def handle(self, *args, **options):
        token = os.getenv('SUPPORT_TELEGRAM_BOT_TOKEN', '').strip()
        if not token:
            raise CommandError('Falta SUPPORT_TELEGRAM_BOT_TOKEN.')
        try:
            data = _post_json(f'https://api.telegram.org/bot{token}/getUpdates', {'limit': 100})
        except SupportIntegrationError as exc:
            raise CommandError(str(exc)) from exc
        if not isinstance(data, dict) or data.get('ok') is not True:
            raise CommandError('Telegram no devolvió los chats recientes.')
        ids = set()
        for update in data.get('result', []):
            chat = ((update.get('message') or {}).get('chat') or {}) if isinstance(update, dict) else {}
            if chat.get('type') == 'private' and isinstance(chat.get('id'), int):
                ids.add(chat['id'])
        for chat_id in sorted(ids):
            self.stdout.write(str(chat_id))
        if not ids:
            self.stdout.write('Sin chats privados recientes. Pedí a cada persona que envíe /start al bot.')
