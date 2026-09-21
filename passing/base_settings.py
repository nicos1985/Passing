"""Non-secret shared settings. Production does not import ignored settings.py/config.py."""

from pathlib import Path

from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_URLCONF = 'passing.urls'
WSGI_APPLICATION = 'passing.wsgi.application'

INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'passbase', 'login', 'permission', 'debug_toolbar', 'notifications', 'django_recaptcha']

MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'debug_toolbar.middleware.DebugToolbarMiddleware']

TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': ['templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'passing.context_processor.counter_admin_notifications', 'passing.context_processor.menu_color']}}]

AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]

LANGUAGE_CODE = 'es-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MESSAGE_TAGS = {messages.DEBUG: 'alert-dark', messages.INFO: 'alert-info', messages.SUCCESS: 'alert-success', messages.WARNING: 'alert-warning', messages.ERROR: 'alert-danger'}

LOGIN_REDIRECT_URL = '/pass/listpass'

AUTH_USER_MODEL = 'login.CustomUser'

MEDIA_URL = '/media/'

ADMIN_ENABLED = True

TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']
