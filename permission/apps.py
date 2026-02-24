"""Configuración de la app `permission`.

Contiene permisos por usuario y roles de permiso que agrupan contraseñas.
"""

from django.apps import AppConfig


class PermissionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'permission'
