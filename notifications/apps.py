from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configura la app `notifications` que gestiona alertas para usuarios y admins."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
