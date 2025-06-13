from django.contrib import admin
from django.urls import path

from notifications.views import  ListNotificationsAdmin, ListNotificationsUser, MarkNotificationsViewed, UpdateNotificationsAdmin, UpdateNotificationsUser, share_contrasena_form


urlpatterns = [
    
    path('create-notif-admin/<int:contrasena>', share_contrasena_form, name='createnotiadmin'),
    path('list-notif-user', ListNotificationsUser.as_view(), name='listnotifuser'),
    path('list-notif-admin', ListNotificationsAdmin.as_view(), name='listnotifadmin'),
    path('marcar-vistas/', MarkNotificationsViewed.as_view(), name='marcar_notificaciones_vistas'),
    
]