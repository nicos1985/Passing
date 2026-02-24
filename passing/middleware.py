from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.db import connection
from django.contrib import messages
from django_tenants.utils import get_public_schema_name
from django.utils.module_loading import import_string
import logging

logger = logging.getLogger(__name__)


class AdminAccessMiddleware:
    """
    Middleware para restringir el acceso a /admin/ basado en la configuración en la base de datos.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):  # Solo intercepta la URL del admin
            try:
                from accounts.models import TenantSettings
                # Asegúrate de que no estamos en el esquema 'public'
                if connection.schema_name != 'public':
                    tenant = getattr(connection, 'tenant', None)
                    ts = TenantSettings.for_client(tenant)
                    if not ts or not ts.is_admin_dash_active:
                        return HttpResponseForbidden("El acceso al panel de administración está deshabilitado.")
                else:
                    return HttpResponseForbidden("El acceso al panel de administración está deshabilitado error 403.")
            except Exception as e:
                logger.exception("Error al verificar acceso al admin")
                return HttpResponseForbidden("No se puede verificar el acceso al admin.")

        return self.get_response(request)




class TenantRouteMiddleware:
    """Middleware para restringir rutas según si es tenant o dominio principal (Public)."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_tenant = hasattr(connection, 'tenant') and connection.tenant.schema_name != "public"

        # Bloquear client-register/ en tenants
        if is_tenant and request.path.startswith("/client-register/"):
            messages.warning(request,"No puedes registrar clientes desde tu cuenta.")
            return redirect('login')
        
        # Bloquear home/ en tenants
        if is_tenant and request.path.startswith("/home/"):
            messages.warning(request,"No puedes acceder a home en tu cuenta.")
            return redirect('login')

        # Bloquear login/ en dominio principal
        if not is_tenant and request.path.startswith("/login/"):
            messages.warning(request,"El login solo está disponible para ingresar en tu cuenta.")
            return redirect('home')
            

        return self.get_response(request)


from django.db import connection
from django.conf import settings

class TenantDebugMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        host = request.get_host()
        schema = getattr(connection, "schema_name", None)
        urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
        logger.debug("[TENANTDBG] host=%s schema=%s urlconf=%s", host, schema, urlconf)
        return self.get_response(request)


class ForceTenantUrlconfMiddleware:
    """
    Si TenantMainMiddleware ya resolvió el schema, garantizamos que request.urlconf
    apunte al URLConf correcto (public vs tenant). Evita que quede pegado en urls_public.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        schema = getattr(connection, "schema_name", None)
        if schema:
            if schema == get_public_schema_name():
                request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", settings.ROOT_URLCONF)
            else:
                request.urlconf = getattr(settings, "TENANT_URLCONF", settings.ROOT_URLCONF)
        return self.get_response(request)


from django.utils import translation


class UserLanguageMiddleware:
    """Middleware que aplica la preferencia de idioma almacenada en el perfil del usuario.

    Comportamiento:
    - Si el usuario está autenticado y tiene `user.language`, activa ese idioma en la request
      y lo guarda en la sesión (para persistir mientras dure la sesión).
    - No sobrescribe una preferencia de idioma establecida manualmente por URL o cookie en la misma request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.user.is_authenticated:
                lang = getattr(request.user, 'language', None)
                # Si ya hay lenguaje en la sesión/cookie, no lo sobrescribimos
                session_key = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
                session_lang = request.session.get(session_key)
                if lang and (not session_lang or session_lang != lang):
                    translation.activate(lang)
                    request.LANGUAGE_CODE = lang
                    request.session[session_key] = lang
        except Exception:
            # Ningún fallo debe bloquear la request; loguear si es necesario
            pass

        response = self.get_response(request)
        return response

