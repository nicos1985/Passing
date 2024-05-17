from notifications.models import AdminNotification, UserNotifications

def counter_admin_notifications(request):
    contador = AdminNotification.objects.filter(type_user=1, viewed=False).count()
    return {'contador_notis': contador}


