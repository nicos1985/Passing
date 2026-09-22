"""Validate production configuration in an isolated process with fake secrets."""
import os
from pathlib import Path
import subprocess
import sys

from cryptography.fernet import Fernet
from django.test import SimpleTestCase


class ProductionConfigurationTests(SimpleTestCase):
    def environment(self):
        return {**os.environ,
                'DJANGO_SETTINGS_MODULE': 'passing.production',
                'DJANGO_SECRET_KEY': 'synthetic-production-test-' * 4,
                'CRYPTOGRAPHY_KEY': Fernet.generate_key().decode(),
                'DJANGO_ALLOWED_HOSTS': 'passing.example.test',
                'DJANGO_DB_ENGINE': 'django.db.backends.sqlite3',
                'DJANGO_DB_PATH': str(Path(__file__).resolve().parent.parent / '.local' / 'synthetic-production-test.sqlite3'),
                'EMAIL_HOST': 'smtp.example.test', 'EMAIL_HOST_USER': 'test@example.test',
                'EMAIL_HOST_PASSWORD': 'synthetic-only', 'DEFAULT_FROM_EMAIL': 'test@example.test',
                'RECAPTCHA_PUBLIC_KEY': 'synthetic-only', 'RECAPTCHA_PRIVATE_KEY': 'synthetic-only'}

    def test_secure_production_configuration_and_backend_load(self):
        result = subprocess.run([sys.executable, '-c', '''
import django
django.setup()
from django.conf import settings
from django.core.mail import get_connection
from django.core.management import call_command
assert not settings.DEBUG
assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
assert settings.SESSION_COOKIE_AGE == 86400
assert settings.SECRET_KEY_FALLBACKS == []
assert 'debug_toolbar' not in settings.INSTALLED_APPS
assert get_connection().__class__.__module__ == 'passing.mail_backend'
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.storage import default_storage
assert staticfiles_storage.file_permissions_mode == 0o644
assert default_storage.file_permissions_mode == 0o600
from django.contrib.staticfiles.finders import find
assert 'django' in find('admin/js/core.js')
assert not find('admin/js/core.js').startswith(str(settings.BASE_DIR / 'static'))
call_command('check', deploy=True, fail_level='ERROR')
'''], cwd=Path(__file__).resolve().parent.parent, env=self.environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_production_secret_fails_at_startup(self):
        env = self.environment()
        env.pop('DJANGO_SECRET_KEY')
        result = subprocess.run([sys.executable, '-c', 'import passing.production'],
                                cwd=Path(__file__).resolve().parent.parent, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Falta la variable obligatoria DJANGO_SECRET_KEY', result.stderr)

    def test_database_backend_must_be_explicit(self):
        env = self.environment()
        env.pop('DJANGO_DB_ENGINE')
        result = subprocess.run([sys.executable, '-c', 'import passing.production'],
                                cwd=Path(__file__).resolve().parent.parent, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_DB_ENGINE', result.stderr)

    def test_postgresql_configuration_uses_selected_cluster(self):
        env = self.environment()
        env.update(DJANGO_DB_ENGINE='django.db.backends.postgresql',
                   DJANGO_DB_NAME='passing_test', DJANGO_DB_USER='passing_test',
                   DJANGO_DB_PORT='5433')
        result = subprocess.run([sys.executable, '-c', '''
from passing.production import DATABASES
database = DATABASES['default']
assert database['ENGINE'] == 'django.db.backends.postgresql'
assert database['PORT'] == '5433'
assert database['NAME'] == 'passing_test'
'''], cwd=Path(__file__).resolve().parent.parent, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
