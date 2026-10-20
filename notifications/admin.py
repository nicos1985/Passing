"""Administración simple para visualizar las alertas almacenadas."""

from django.contrib import admin
from .models import UserNotifications, AdminNotification
from passbase.models import Contrasena


class CorporateNotificationAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(id_contrasena__is_personal=False)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'id_contrasena':
            kwargs['queryset'] = Contrasena.objects.filter(is_personal=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class UserNotificationsAdmin(CorporateNotificationAdmin):
    """Admin para revisar notificaciones enviadas a usuarios comunes."""

    list_display = ('id', 'id_user', 'id_contrasena', 'type_notification', 'viewed')


class AdminNotificationsAdmin(CorporateNotificationAdmin):
    """Admin para monitorear solicitudes enviadas a admins o staff."""

    list_display = ('id', 'id_user', 'id_user_share', 'id_contrasena', 'type_notification', 'viewed')


admin.site.register(UserNotifications, UserNotificationsAdmin)
admin.site.register(AdminNotification, AdminNotificationsAdmin)