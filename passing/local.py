"""Development settings. Start with scripts/run-local.ps1, bound to loopback only."""

from copy import deepcopy

from .settings import *  # noqa: F403
from .mfa_settings import configure
import secrets

LOCAL_DEVELOPMENT = True
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
INTERNAL_IPS = []
LOCAL_DIR = BASE_DIR / '.local'
LOCAL_DIR.mkdir(exist_ok=True)
# A development signing key must not reuse a key exposed in repository history.
_signing_key = LOCAL_DIR / 'django-secret-key'
if not _signing_key.exists():
    try:
        with _signing_key.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
SECRET_KEY = _signing_key.read_text(encoding='utf-8').strip()
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': LOCAL_DIR / 'db.sqlite3'}}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'passing@localhost'
MEDIA_ROOT = LOCAL_DIR / 'media'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = LOCAL_DIR / 'static-collected'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_NAME = 'passing_local_session'
CSRF_COOKIE_NAME = 'passing_local_csrf'
TEMPLATES = deepcopy(TEMPLATES)
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']
LOGGING = deepcopy(LOGGING)
LOGGING['handlers']['file']['filename'] = str(LOCAL_DIR / 'debug.log')
configure(globals())
