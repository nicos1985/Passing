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
    color = '#212629'  # Color por defecto
    company = None  # Empresa por defecto

    try:
        # Intentar obtener la configuración global
        settings = GlobalSettings.objects.filter(id=1).first()
        
        if settings:
            color = settings.menu_color if settings.menu_color else '#212629'
            company = settings.company_name if settings.company_name else None

    except Exception as e:
        print(f"Error en menu_color: {e}")  # Para depuración

    return {'color': color, 'company': company}

