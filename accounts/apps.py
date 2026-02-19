from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configura la aplicación `accounts` que gestiona autenticación y SSO en el hub."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
