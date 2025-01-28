from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.db import connection

class AdminAccessMiddleware:
    """
    Middleware para restringir el acceso a /admin/ basado en la configuración en la base de datos.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):  # Solo intercepta la URL del admin
            try:
                from login.models import GlobalSettings
                # Asegúrate de que no estamos en el esquema 'public'
                if connection.schema_name != 'public':
                    settings = GlobalSettings.objects.filter(is_active=True).last()
                    if not settings or not settings.is_admin_dash_active:
                        # Opciones: redirigir o devolver un error 403
                        return HttpResponseForbidden("El acceso al panel de administración está deshabilitado.")
                else:
                    return HttpResponseForbidden("El acceso al panel de administración está deshabilitado error 403.")
            except Exception as e:
                print(f"Error al verificar acceso al admin: {e}")
                return HttpResponseForbidden("No se puede verificar el acceso al admin.")

        return self.get_response(request)
