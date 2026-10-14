from django.contrib import admin
from django.urls import path

from notifications.views import  ListNotificationsAdmin, ListNotificationsUser, MarkNotificationsViewed, UpdateNotificationsAdmin, UpdateNotificationsUser, share_contrasena_form, notification_inbox, open_inbox_notice, mark_inbox_read, notification_settings, test_notification_email


urlpatterns = [
    path('', notification_inbox, name='notification_inbox'),
    path('open/<int:pk>/', open_inbox_notice, name='open_inbox_notice'),
    path('mark-read/', mark_inbox_read, name='mark_inbox_read'),
    path('settings/', notification_settings, name='notification_settings'),
    path('settings/test-email/', test_notification_email, name='test_notification_email'),
    
    path('create-notif-admin/<int:contrasena>', share_contrasena_form, name='createnotiadmin'),
    path('list-notif-user', ListNotificationsUser.as_view(), name='listnotifuser'),
    path('list-notif-admin', ListNotificationsAdmin.as_view(), name='listnotifadmin'),
    path('marcar-vistas/', MarkNotificationsViewed.as_view(), name='marcar_notificaciones_vistas'),
    
]
