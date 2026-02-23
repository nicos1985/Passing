import os

# Minimal settings for extracting translations without full project apps
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = 'i18n-temporary-key'

DEBUG = False

INSTALLED_APPS = []

USE_I18N = True
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [],
        },
    }
]

STATIC_URL = '/static/'
