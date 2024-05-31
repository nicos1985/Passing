from django.contrib import admin

# Register yofrom .models import CustomUser
from .models import UserNotifications, AdminNotification
class UserNotificationsAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_user', 'id_contra')

class AdminNotificationsAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_user', 'id_user_share', 'id_contra')


admin.site.register(UserNotifications ,AdminNotification, UserNotificationsAdmin, AdminNotificationsAdmin ) #ur models here.
