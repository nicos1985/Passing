from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configura la aplicación `accounts` que gestiona autenticación y SSO en el hub."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    def ready(self):
        # Import signals to register post/pre save hooks
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid crashing on import during manage.py commands if migrations not applied
            pass
