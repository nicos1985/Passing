"""Configuraciones de admin para modelos de `passbase`."""

from django.contrib import admin
from django.db.models import Q
from .models import Contrasena, LogData, SeccionContra


class ContrasenaAdmin(admin.ModelAdmin):
    """Admin para inspeccionar contraseñas (campos sensibles se muestran como cifrados)."""

    list_display = ('id', 'nombre_contra', 'seccion', 'info', 'usuario')
    readonly_fields = ('created', 'updated')
    search_fields = ('nombre_contra', 'hash')
    list_filter = ('created', 'seccion')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(Q(is_personal=False) | Q(owner=request.user))

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_personal:
            fields.append('owner')
        if obj and obj.owner_id != request.user.pk:
            fields.append('is_personal')
        return fields


class LogDataAdmin(admin.ModelAdmin):
    """Admin para revisar logs de auditoría."""

    list_display = ('contraseña', 'entidad', 'usuario', 'action', 'created')
    readonly_fields = ('created',)

    def get_queryset(self, request):
        private_ids = Contrasena.objects.filter(is_personal=True).exclude(owner=request.user).values_list('pk', flat=True)
        return super().get_queryset(request).exclude(
            entidad__in=('Contrasena', 'Contraseña'), contraseña__in=private_ids,
        )


class SeccionContAdmin(admin.ModelAdmin):
    """Admin para administrar secciones de contraseñas."""

    list_display = ('nombre_seccion',)
    readonly_fields = ('created', 'updated')


admin.site.register(SeccionContra, SeccionContAdmin)
admin.site.register(Contrasena, ContrasenaAdmin)
admin.site.register(LogData, LogDataAdmin)
