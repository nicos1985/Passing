"""Administración simple para visualizar las alertas almacenadas."""

from django.contrib import admin
from .models import UserNotifications, AdminNotification


class UserNotificationsAdmin(admin.ModelAdmin):
    """Admin para revisar notificaciones enviadas a usuarios comunes."""

    list_display = ('id', 'id_user', 'id_contrasena', 'type_notification', 'viewed')


class AdminNotificationsAdmin(admin.ModelAdmin):
    """Admin para monitorear solicitudes enviadas a admins o staff."""

    list_display = ('id', 'id_user', 'id_user_share', 'id_contrasena', 'type_notification', 'viewed')


admin.site.register(UserNotifications, UserNotificationsAdmin)
admin.site.register(AdminNotification, AdminNotificationsAdmin)