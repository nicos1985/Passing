"""Offline transactional re-encryption. Never output keys or decrypted values."""
import os
import re
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from passbase.crypto import _token
from passbase.models import Contrasena, LogData


class Command(BaseCommand):
    help = 'Validate and re-encrypt vault + audit data; dry-run unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--backup-confirmed', action='store_true')

    def handle(self, **options):
        if options['apply'] and not options['backup_confirmed']:
            raise CommandError('Detené los workers y verificá un backup antes de usar --backup-confirmed.')
        try:
            old = Fernet(settings.CRYPTOGRAPHY_KEY)
            new_key = os.environ['PASSING_NEW_CRYPTOGRAPHY_KEY']
            new = Fernet(new_key)
        except (KeyError, ValueError):
            raise CommandError('Configurá PASSING_NEW_CRYPTOGRAPHY_KEY con una nueva clave Fernet.') from None
        current = settings.CRYPTOGRAPHY_KEY
        if new_key.encode() == (current.encode() if isinstance(current, str) else current):
            raise CommandError('La nueva clave debe ser distinta.')

        def rotate(value):
            if not value:
                return value
            plain = old.decrypt(_token(value))
            encrypted = new.encrypt(plain)
            if new.decrypt(encrypted) != plain:
                raise CommandError('Falló la verificación del recifrado.')
            return str(encrypted)

        try:
            with transaction.atomic():
                credentials = logs = 0
                for record in Contrasena.objects.select_for_update().iterator():
                    data = {'usuario': rotate(record.usuario), 'contraseña': rotate(record.contraseña), 'hash': None}
                    if options['apply']:
                        Contrasena.objects.filter(pk=record.pk).update(**data)
                    credentials += 1
                for record in LogData.objects.select_for_update().iterator():
                    password = rotate(record.password)
                    detail = re.sub(r"Usuario: (b'gAAAA[^']*'),", lambda m: 'Usuario: ' + rotate(m[1]) + ',', record.detail)
                    # Do not silently retain a historical plaintext username in audit data.
                    if 'Usuario: ' in detail and not re.search(r"Usuario: b'gAAAA[^']*',", detail):
                        raise CommandError(f'Log {record.pk}: formato histórico no reconocido; requiere revisión offline.')
                    if options['apply']:
                        LogData.objects.filter(pk=record.pk).update(password=password, detail=detail)
                    logs += 1
        except (InvalidToken, TypeError, UnicodeError):
            raise CommandError('Registro inválido o clave incorrecta. No se guardó ningún cambio.') from None
        self.stdout.write(f"{'APLICADO' if options['apply'] else 'DRY-RUN'}: {credentials} credenciales, {logs} logs verificados.")
        if options['apply']:
            self.stdout.write('Actualizá CRYPTOGRAPHY_KEY en el servicio antes de reiniciar los workers.')
