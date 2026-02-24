from django.apps import AppConfig


class ThreatIntelConfig(AppConfig):
    """Configuración base para el módulo de inteligencia de amenazas."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'threat_intel'
    verbose_name = 'Inteligencia de amenazas'
