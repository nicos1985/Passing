# passing/settings.py

from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
# =========================
# Básicos
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga variables de entorno desde .env (solo para desarrollo/local)
load_dotenv(BASE_DIR / ".env")

# DEBUG desde entorno (usar DJANGO_DEBUG=0/1 en producción)
DJANGO_DEBUG = os.getenv("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes"}
DEBUG = DJANGO_DEBUG

# SECRET_KEY debe provenir del entorno en producción. En desarrollo se permite un valor "dev" temporal.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("SECRET_KEY must be set in environment for production")
    # Valor temporal para desarrollo local (no usar en producción)
    SECRET_KEY = "dev-secret-placeholder"
if not DEBUG and len(SECRET_KEY) < 50:
    raise RuntimeError("SECRET_KEY must have at least 50 characters in production")

# ALLOWED_HOSTS configurable por entorno, por defecto localhost para desarrollo
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
if not DEBUG and (not ALLOWED_HOSTS or any("*" in host or "/" in host for host in ALLOWED_HOSTS)):
    raise RuntimeError("Set explicit ALLOWED_HOSTS for production")

# Durante desarrollo, permitir subdominios de localhost (p.ej. test.localhost)
if DEBUG:
    if ".localhost" not in ALLOWED_HOSTS and ".localhost" not in ",".join(ALLOWED_HOSTS):
        ALLOWED_HOSTS.append(".localhost")

INTERNAL_IPS = ["127.0.0.1"]

# CRYPTOGRAPHY_KEY: valor URL-safe base64 desde entorno (no guardar en repo)
_crypto_env = os.getenv("CRYPTOGRAPHY_KEY")
if _crypto_env:
    CRYPTOGRAPHY_KEY = _crypto_env.encode() if isinstance(_crypto_env, str) else _crypto_env
else:
    CRYPTOGRAPHY_KEY = None
if not DEBUG:
    from cryptography.fernet import Fernet
    if not CRYPTOGRAPHY_KEY:
        raise RuntimeError("CRYPTOGRAPHY_KEY must be set in production")
    Fernet(CRYPTOGRAPHY_KEY)

# =========================
# Tenants (django-tenants)
# =========================
TENANT_MODEL = "client.Client"
TENANT_DOMAIN_MODEL = "client.Domain"

# URLConfs separados
PUBLIC_SCHEMA_URLCONF = "passing.urls_public"   # hub (allauth, accounts)
TENANT_URLCONF = "passing.urls_tenant"          # app del tenant
ROOT_URLCONF = "passing.urls_public"            # raíz = público

SHOW_PUBLIC_IF_NO_TENANT_FOUND = False  # fallback al hub si el dominio no matchea

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.getenv("DATABASE_NAME", "dev"),
        "USER": os.getenv("DATABASE_USER", "postgres"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", ""),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
    }
}

DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

# =========================
# Apps compartidas vs tenant
# =========================
# IMPORTANTE: 'django_tenants' primero en INSTALLED_APPS (y en SHARED_APPS).
SHARED_APPS = [
    "django_tenants",
    "client",  # Client & Domain viven en PUBLIC
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Autenticación global (usuarios en PUBLIC)
    "django.contrib.auth",
    "django.contrib.sessions",  # sesiones compartidas en PUBLIC
    "django.contrib.admin",
    "django.contrib.messages",

    # Terceros (compartidos)
    "debug_toolbar",
    "django_recaptcha",

    # Allauth + hub
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    # Tu app de usuarios globales, settings del tenant, auditoría, etc.
    "accounts",
]

TENANT_APPS = [
    # Apps con datos por schema (se instalan en cada tenant)
    "login",          # incluye /sso/consume y /sso/verify-2fa
    "permission",
    "notifications",
    "resources",
    "passbase",
    "threat_intel",   # inteligencia de amenazas
    "docmanager",      # gestión documental
    "monitoring",     # disponibilidad de servicios
    "supporthub",     # bandeja y avisos de soporte Bitrix24
]

INSTALLED_APPS = SHARED_APPS + TENANT_APPS
if not DEBUG:
    INSTALLED_APPS.remove("debug_toolbar")

SITE_ID = 1  # Site del hub público (para allauth)




# =========================
# Middleware (orden importa)
# =========================
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "passing.middleware.ForceTenantUrlconfMiddleware",
    "passing.middleware.TenantDebugMiddleware",  # debe ir bien arriba
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "passing.middleware.UserLanguageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "login.middleware.TwoFactorAuthMiddleware",  # obliga a completar 2FA tras autenticación
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",  # solo tiene efecto con DEBUG
]
if not DEBUG:
    MIDDLEWARE.remove("debug_toolbar.middleware.DebugToolbarMiddleware")

# =========================
# Templates
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # tu base.html vive acá
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",   # requerido por allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "passing.context_processor.counter_admin_notifications",
                "passing.context_processor.menu_color",
                "passing.context_processor.tenant_context",
            ],
        },
    },
]

WSGI_APPLICATION = "passing.wsgi.application"

# =========================
# Auth / Allauth / SSO
# =========================
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",  # login programático (SSO)
    "allauth.account.auth_backends.AuthenticationBackend",
    "permission.backends.ModuleRoleBackend",
]
HUB_ORIGIN = os.getenv("HUB_ORIGIN", "http://localhost:8000").rstrip("/")
if not DEBUG:
    _hub_url = urlparse(HUB_ORIGIN)
    if _hub_url.scheme != "https" or not _hub_url.hostname or _hub_url.path or _hub_url.query:
        raise RuntimeError("HUB_ORIGIN must be an HTTPS origin in production")
LOGIN_URL = f"{HUB_ORIGIN}/accounts/"
LOGIN_REDIRECT_URL = "/accounts/post-login/"

ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAdapter"

# Sin registro por allauth; igual reforzado por AccountAdapter.is_open_for_signup=False
# Deprecated settings (replaced with ACCOUNT_LOGIN_METHODS and ACCOUNT_SIGNUP_FIELDS)
# See warnings: use ACCOUNT_LOGIN_METHODS and ACCOUNT_SIGNUP_FIELDS instead
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # no hacemos verificación aquí (tu flujo propio)

SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["openid", "email", "profile"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}

# Handoff SSO hub->tenant
SSO_SIGNING_SALT = "sso-xfer-v1"
SSO_TRANSFER_TTL_SECONDS = 90
SSO_LOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"

# =========================
# Sesiones / Cookies DEV
# =========================
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 24 * 60 * 60  # 24 horas desde la última actividad
SESSION_SAVE_EVERY_REQUEST = True

# Sesión / Cookies: en producción habilitar flags de seguridad
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", None)
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", None)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
if not DEBUG and any(not origin.startswith("https://") or "*" in origin for origin in CSRF_TRUSTED_ORIGINS):
    raise RuntimeError("CSRF_TRUSTED_ORIGINS must contain explicit HTTPS origins")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "3600" if not DEBUG else "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only when the HTTPS reverse proxy overwrites X-Forwarded-Proto.
if not DEBUG and os.getenv("DJANGO_TRUST_PROXY_HTTPS") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

# =========================
# I18N / TZ
# =========================
# Idioma por defecto del proyecto
LANGUAGE_CODE = "es"

# Zonas horarias y localización
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Idiomas soportados (UI únicamente)
LANGUAGES = [
    ("es", "Español"),
    ("en", "English"),
]

# Ruta para catálogos de traducción generados por `makemessages`
LOCALE_PATHS = [BASE_DIR / "locale"]

#==========================
#  Threat Intel
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RISK_ASSISTANT_AI_ENABLED = os.getenv('RISK_ASSISTANT_AI_ENABLED', 'true').lower() in {'1', 'true', 'yes'}
THREAT_INTEL = {
    "ENABLED_SOURCES": ["NVD", "AWS"],  # luego "FORTINET"
    "DEFAULT_DAYS": 30,
    "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    "EMAIL_RECIPIENTS": ["tecnologia@previ.com.ar"],  # luego agregás Dirección
    "EMAIL_SUBJECT_PREFIX": "[SGSI] Threat Intel",
    "ENABLE_AI_ANALYSIS": True,  # prendelo cuando tengas la key y el prompt afinado
    "AI_MEDIUM_TOP_N": 10,
    "AI_MAX_ITEMS": 5,           # solo para pruebas iniciales
}



# =========================
# Static / Media (tenants)
# =========================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Recomendado definir STATIC_ROOT para collectstatic
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# FileField uploads are tenant-scoped. Application static assets are global.
STORAGES = {
    "default": {"BACKEND": "django_tenants.files.storage.TenantFileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# =========================
# Emails
# =========================
# Load email configuration from environment (or fallback to console backend)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", os.getenv("EMAIL_HOST_USER", ""))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", os.getenv("EMAIL_HOST_USER", "noreply@localhost"))
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Choose backend: SMTP if credentials present, otherwise console backend
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
if not DEBUG:
    if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        raise RuntimeError("Configure a real EMAIL_BACKEND for production")
    if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and (
        not os.getenv("EMAIL_HOST") or not os.getenv("DEFAULT_FROM_EMAIL")
    ):
        raise RuntimeError("Configure EMAIL_HOST and DEFAULT_FROM_EMAIL for production SMTP")

# =========================
# Threat Intelligence Email Config
# =========================
# Email backend for threat intel reports: "smtp" (default) or "brevo"
THREAT_INTEL_EMAIL_BACKEND = os.getenv("THREAT_INTEL_EMAIL_BACKEND", "smtp")

# Brevo (SendinBlue) API Key - Add to environment variables
# export BREVO_API_KEY="your-api-key-here"
BREVO_API_KEY = os.getenv("BREVO_API_KEY", None)

# Email sender name for Brevo (if using Brevo backend)
DEFAULT_FROM_NAME = "Threat Intel System"

# =========================
# Debug Toolbar
# =========================
DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]

# =========================
# ReCaptcha (configurable)
# =========================
RECAPTCHA_TESTING = os.getenv("RECAPTCHA_TESTING", "1" if DEBUG else "0").lower() in ("1", "true", "yes")
if not DEBUG and RECAPTCHA_TESTING:
    raise RuntimeError("RECAPTCHA_TESTING cannot be enabled in production")
RECAPTCHA_PUBLIC_KEY = os.getenv("RECAPTCHA_PUBLIC_KEY", "")
RECAPTCHA_PRIVATE_KEY = os.getenv("RECAPTCHA_PRIVATE_KEY", "")
if not DEBUG and (not RECAPTCHA_PUBLIC_KEY or not RECAPTCHA_PRIVATE_KEY):
    raise RuntimeError("Configure RECAPTCHA_PUBLIC_KEY and RECAPTCHA_PRIVATE_KEY for production")
DOCMANAGER_WEBHOOK_TOKEN = os.getenv("DOCMANAGER_WEBHOOK_TOKEN", "")
DOCMANAGER_DRIVE_ENABLED = False
TENANT_REGISTRATION_ENABLED = False

# =========================
# Misc propios
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
GRAN_PERMISSION_ID_USERS = [1] if DEBUG else []

# Flags dev/prod propios (si los usás)
SSO_USE_HANDOFF = True
BROKER_BASE_URL = os.getenv("BROKER_BASE_URL", HUB_ORIGIN).rstrip("/")
TENANT_BASE_URL = os.getenv("TENANT_BASE_URL", "localhost:8000")
TENANT_SCHEME = os.getenv("TENANT_SCHEME", "http" if DEBUG else "https")
if not DEBUG and (not BROKER_BASE_URL.startswith("https://") or TENANT_SCHEME != "https" or "localhost" in TENANT_BASE_URL):
    raise RuntimeError("Configure HTTPS broker and tenant URLs for production")


# Logging: enable debug output to console and to debug.log for local development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact"],
        },

        "file": {
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "debug.log"),
            "formatter": "verbose",
            "filters": ["redact"],
        },
    },
    "filters": {
        "redact": {
            "()": "passing.logging_utils.RedactingFilter",
            "fields": ["otp_secret", "password", "token", "api_key", "access_token"],
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG",
    },
    "loggers": {
        # urllib3 incluye los códigos secretos de los webhooks en la ruta HTTP.
        "urllib3": {"level": "WARNING"},
    },
}
if not DEBUG:
    LOGGING["handlers"].pop("file")
    LOGGING["root"] = {"handlers": ["console"], "level": "WARNING"}
