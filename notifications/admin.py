from django.contrib import admin

# Register yofrom .models import CustomUser
from .models import UserNotifications, AdminNotification
class UserNotificationsAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_user', 'id_contrasena')

class AdminNotificationsAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_user', 'id_user_share', 'id_contrasena')


admin.site.register(UserNotifications ,UserNotificationsAdmin) #ur models here.
admin.site.register(AdminNotification, AdminNotificationsAdmin)