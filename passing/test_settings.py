"""Self-contained tests: no production secrets, database, SMTP or config imports."""
from cryptography.fernet import Fernet
from .base_settings import *  # noqa: F403
from .mfa_settings import configure

DEBUG = False
SECRET_KEY = 'passing-test-only-signing-key-not-for-deployment'
CRYPTOGRAPHY_KEY = Fernet.generate_key()
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
RECAPTCHA_PUBLIC_KEY = 'synthetic-test-key'
RECAPTCHA_PRIVATE_KEY = 'synthetic-test-key'
GRAN_PERMISSION_ID_USERS = []
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']
MIDDLEWARE = [m for m in MIDDLEWARE if not m.startswith('debug_toolbar.')]
configure(globals())
