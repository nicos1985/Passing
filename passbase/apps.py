from django.apps import AppConfig


class PassbaseConfig(AppConfig):
    """Configuración de la aplicación `passbase`.

    Se encarga de registrar señales al iniciarse la app.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'passbase'

    def ready(self):
        # Importar señales aquí para asegurarse de que se registren
        try:
            from . import signals  # noqa: F401
        except Exception:
            # No detener la carga de la app si las señales faltan o fallan
            pass