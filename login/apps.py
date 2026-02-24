from django.apps import AppConfig


class LoginConfig(AppConfig):
    """Configura la app `login` encargada del hub y la gestión de usuarios tenant."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login'
