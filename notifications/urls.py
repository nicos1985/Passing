from django.contrib import admin
from django.urls import path

from notifications.views import CreateNotificationsUser, ListNotificationsAdmin, ListNotificationsUser, UpdateNotificationsAdmin, UpdateNotificationsUser, share_contrasena_form


urlpatterns = [
    
    #path('create-notif-user', CreateNotificationsUser.as_view(), name='createnotifuser'),
    path('create-notif-admin/<int:contrasena>', share_contrasena_form, name='createnotiadmin'),
    #path('list-notif-user', ListNotificationsUser.as_view(), name='listnotifuser'),
    #path('list-notif-admin', ListNotificationsAdmin.as_view(), name='listnotifadmin'),
    #path('update-notif-user', UpdateNotificationsUser.as_view(), name='updatenotifuser'),
    #path('update-notif-admin', UpdateNotificationsAdmin.as_view(), name='updatenotifadmin'),
]