"""Create disposable accounts for manual MFA testing in the isolated local DB."""

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from permission.models import PermissionRoles


class Command(BaseCommand):
    help = 'Create local MFA test accounts without altering existing accounts.'

    def handle(self, *args, **options):
        expected_db = settings.BASE_DIR / '.local' / 'db.sqlite3'
        if (not settings.DEBUG or not getattr(settings, 'LOCAL_DEVELOPMENT', False)
                or str(settings.DATABASES['default']['NAME']) != str(expected_db)):
            raise CommandError('Este comando solo se puede usar con --settings=passing.local.')
        credentials = settings.LOCAL_DIR / 'accounts.txt'
        rows = []
        with transaction.atomic():
            role, _ = PermissionRoles.objects.get_or_create(rol_name='Pruebas locales')
            for username, administrator in (('admin_local', True), ('admin_respaldo', True),
                                             ('usuario_local', False)):
                if get_user_model().objects.filter(username=username).exists():
                    continue
                password = secrets.token_urlsafe(18)
                get_user_model().objects.create_user(
                    username=username, email=f'{username}@example.test', password=password,
                    assigned_role=role, is_staff=administrator, is_superuser=administrator,
                )
                rows.append(f'{username}: {password}\n')
            if rows:
                with credentials.open('a', encoding='utf-8') as output:
                    output.writelines(rows)
        self.stdout.write(self.style.SUCCESS('Entorno local listo.'))
        self.stdout.write(f'Usuarios y contraseñas: {credentials}')
        self.stdout.write('No se modificaron las contraseñas ni los autenticadores existentes.')
