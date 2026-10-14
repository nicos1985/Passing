from django.apps import AppConfig


class ResourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'resources'

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
