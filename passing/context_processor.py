from notifications.models import AdminNotification, UserNotifications

def counter_admin_notifications(request):
    contador = AdminNotification.objects.filter(type_user=1, viewed=False).count()
    if request.user.is_authenticated:
        contador_notis_user = UserNotifications.objects.filter(id_user = request.user, viewed=False).count()
    else:
        contador_notis_user = 0
    return {'contador_notis': contador, 'contador_notis_user' : contador_notis_user}


