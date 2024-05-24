from notifications.models import AdminNotification, UserNotifications

def counter_admin_notifications(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            contador_notis = AdminNotification.objects.filter(type_user=1, viewed=False).count()
        else:
            contador_notis= UserNotifications.objects.filter(id_user = request.user, viewed=False).count()
    else:
        contador_notis = 0
    return {'contador_notis': contador_notis}


