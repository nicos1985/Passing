from notifications.models import AdminNotification, UserNotifications
from accounts.models import TenantSettings
import logging

logger = logging.getLogger(__name__)

DEFAULT_MENU_COLOR = "#212629"

def counter_admin_notifications(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            try:
                contador_notis = AdminNotification.objects.filter(type_user=1, viewed=False).count()
            except Exception as e:
                logger.exception('Error en counter_admin_notifications')
                return {'contador_notis': 0}
        else:
            try:
                contador_notis = UserNotifications.objects.filter(id_user=request.user, viewed=False).count()
            except Exception as e:
                logger.exception('Error en counter_user_notifications')
                return {'contador_notis': 0}
    else:
        contador_notis = 0
    return {'contador_notis': contador_notis}

def menu_color(request):
    color = DEFAULT_MENU_COLOR
    company = None
    company_logo = None

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
                company_logo = None
                try:
                    if getattr(ts, 'company_logo', None):
                        company_logo = ts.company_logo.url
                except Exception:
                    company_logo = None
    except Exception:
        # podés loguear si querés
        pass

    return {"color": color, "company": company, "company_logo": company_logo}


def tenant_context(request):
    tenant = getattr(request, "tenant", None)
    return {
        "tenant_schema": getattr(tenant, "schema_name", "public"),
        # útil si lo querés en templates:
        "tenant_company": getattr(getattr(tenant, "settings", None), "company_name", None),
    }

