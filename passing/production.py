"""Production settings. Environment variables are supplied by the service manager."""
import os
from django.core.exceptions import ImproperlyConfigured
from .base_settings import *  # noqa: F403
from .mfa_settings import configure


def required(name):
    value = os.environ.get(name, '')
    if not value:
        raise ImproperlyConfigured(f'Falta la variable obligatoria {name}')
    return value


DEBUG = False
LOCAL_DEVELOPMENT = False
SECRET_KEY = required('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY debe tener al menos 50 caracteres aleatorios.')
SECRET_KEY_FALLBACKS = []
CRYPTOGRAPHY_KEY = required('CRYPTOGRAPHY_KEY')
from cryptography.fernet import Fernet
Fernet(CRYPTOGRAPHY_KEY)  # Fail at startup rather than while opening the vault.
ALLOWED_HOSTS = required('DJANGO_ALLOWED_HOSTS').split(',')
if any(not h.strip() or '*' in h or '/' in h for h in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Configurá hosts explícitos, sin comodines ni esquemas.')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = [v for v in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if v]
if any(not v.startswith('https://') or '*' in v for v in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('Los orígenes CSRF deben ser HTTPS explícitos.')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Enable only behind a trusted proxy that OVERWRITES this header.
if os.environ.get('DJANGO_TRUST_PROXY_HTTPS') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
TRUSTED_PROXY_IPS = [v.strip() for v in os.environ.get('DJANGO_TRUSTED_PROXY_IPS', '').split(',') if v.strip()]
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != 'debug_toolbar']
MIDDLEWARE = [m for m in MIDDLEWARE if not m.startswith('debug_toolbar.')]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': os.environ.get('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3'))}}
MEDIA_ROOT = os.environ.get('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'media'))
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static-collected'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'passing.storage.PublicStaticFilesStorage'},
}
EMAIL_BACKEND = 'passing.mail_backend.EmailBackend'
EMAIL_HOST = required('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', '0') == '1'
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured('Activá TLS o SSL para SMTP, solo uno.')
EMAIL_HOST_USER = required('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = required('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = required('DEFAULT_FROM_EMAIL')
EMAIL_TIMEOUT = 20
RECAPTCHA_PUBLIC_KEY = required('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = required('RECAPTCHA_PRIVATE_KEY')
GRAN_PERMISSION_ID_USERS = []  # No implicit access grants to hardcoded user IDs.
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'standard': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {name: {'handlers': ['console'], 'level': 'INFO', 'propagate': False}
                for name in ('django', 'passing.mail', 'passing.security')},
}
configure(globals())
