from notifications.models import AdminNotification, UserNotifications
from accounts.models import TenantSettings

DEFAULT_MENU_COLOR = "#212629"

def counter_admin_notifications(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            try:
                contador_notis = AdminNotification.objects.filter(type_user=1, viewed=False).count()
            except Exception as e:
                return {'contador_notis': 0}
                print(f"Error en counter_admin_notifications: {e}")
        else:
            try:
                contador_notis = UserNotifications.objects.filter(id_user=request.user, viewed=False).count()
            except Exception as e:
                return {'contador_notis': 0}
                print(f"Error en counter_user_notifications: {e}")
    else:
        contador_notis = 0
    return {'contador_notis': contador_notis}

def menu_color(request):
    color = DEFAULT_MENU_COLOR
    company = None

    try:
        tenant = getattr(request, "tenant", None)
        if tenant:
            ts = getattr(tenant, "settings", None)
            if ts is None:
                # fallback por si todavía no existe o no está creada
                ts = TenantSettings.objects.filter(client_id=tenant.id).first()

            if ts:
                color = ts.menu_color or DEFAULT_MENU_COLOR
                company = ts.company_name or None
    except Exception:
        # podés loguear si querés
        pass

    return {"color": color, "company": company}


def tenant_context(request):
    tenant = getattr(request, "tenant", None)
    return {
        "tenant_schema": getattr(tenant, "schema_name", "public"),
        # útil si lo querés en templates:
        "tenant_company": getattr(getattr(tenant, "settings", None), "company_name", None),
    }

