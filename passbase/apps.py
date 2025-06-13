from django.apps import AppConfig


class PassbaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'passbase'


def ready(self):
    from .import signals