from notifications.models import AdminNotification, UserNotifications
from login.models import GlobalSettings

def counter_admin_notifications(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            contador_notis = AdminNotification.objects.filter(type_user=1, viewed=False).count()
        else:
            contador_notis= UserNotifications.objects.filter(id_user = request.user, viewed=False).count()
    else:
        contador_notis = 0
    return {'contador_notis': contador_notis}

def menu_color(request):
    if request.user.is_anonymous:
        color = '#212629'

    else:
        settings = GlobalSettings.objects.get(id=1)
        if settings.menu_color == None:
            color = request.user.menu_color
        else:
            color = settings.menu_color
    
    return {'color': color}


