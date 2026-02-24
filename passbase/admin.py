"""Configuraciones de admin para modelos de `passbase`."""

from django.contrib import admin
from .models import Contrasena, LogData, SeccionContra


class ContrasenaAdmin(admin.ModelAdmin):
    """Admin para inspeccionar contraseñas (campos sensibles se muestran como cifrados)."""

    list_display = ('id', 'nombre_contra', 'seccion', 'info', 'usuario')
    readonly_fields = ('created', 'updated')
    search_fields = ('nombre_contra', 'hash')
    list_filter = ('created', 'seccion', 'usuario', 'hash')


class LogDataAdmin(admin.ModelAdmin):
    """Admin para revisar logs de auditoría."""

    list_display = ('contraseña', 'entidad', 'usuario', 'action', 'created')
    readonly_fields = ('created',)


class SeccionContAdmin(admin.ModelAdmin):
    """Admin para administrar secciones de contraseñas."""

    list_display = ('nombre_seccion',)
    readonly_fields = ('created', 'updated')


admin.site.register(SeccionContra, SeccionContAdmin)
admin.site.register(Contrasena, ContrasenaAdmin)
admin.site.register(LogData, LogDataAdmin)
