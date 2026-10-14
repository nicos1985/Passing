import re
from urllib.parse import urlparse
from django.forms import ValidationError
from django.shortcuts import redirect, render
from django.http import Http404, HttpResponse
from django.contrib import messages
from client.models import Client, Domain
from accounts.models import TenantSettings
from .forms import ClientRegisterForm
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
import logging
from django.utils import translation
from django.conf import settings
from django.shortcuts import HttpResponseRedirect
from django.middleware.csrf import get_token
# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#######################################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



def home(request):
    return render(request, 'home.html')

def landing(request):
    return render(request, 'landing.html')

def home_tenant(request):
    return redirect('login')

def config(request):
    return render(request, 'admin.html')

def clean_domain_name(name, schema=False):
    """
    Limpia un nombre para que sea válido como dominio:
    - Solo permite letras, números y guiones.
    - Convierte espacios en guiones.
    - Elimina caracteres no permitidos.
    - Si Schema True, entonces los espacios se transforman 
    en guiones bajos
    """
    if schema:
        # Reemplazar espacios con guiones bajos
        name = name.replace(' ', '_')
    else:
        # Reemplazar espacios con guiones
        name = name.replace(' ', '-')
    
    # Eliminar caracteres no permitidos
    name = re.sub(r'[^a-zA-Z0-9\-]', '', name)
    
    # Asegurarse de que no empiece ni termine con un guion
    name = name.strip('-')
    
    return name.lower()


def validate_unique_schema_name(nom_schema, nom_empresa):
    if Client.objects.filter(schema_name=nom_schema).exists():
        raise ValidationError(f'El nombre "{nom_empresa}" ya existe. Por favor, elige otro nombre de empresa.')

def client_register(request):
    if not settings.TENANT_REGISTRATION_ENABLED:
        raise Http404("El registro de nuevos tenants está deshabilitado.")
    if request.method == 'POST':
        form = ClientRegisterForm(request.POST)
        if form.is_valid():
              # Guarda el cliente en la base de datos
            instance = form.save(commit=False)
            client_name = form.cleaned_data['client_name']
            instance.schema_name = clean_domain_name(client_name, schema=True)
            try:
                validate_unique_schema_name(instance.schema_name, client_name)
            except Exception as e:
                messages.error(request, f'Error al crear el cliente: {e}')
                return redirect('client_register')
            instance.save()
            # Crear TenantSettings inmediatamente para evitar accesos intermedios sin settings
            try:
                TenantSettings.objects.get_or_create(client=instance)
            except Exception:
                # No fatal: continuar y loguear si se desea
                pass
            
            base_domain = urlparse(request.build_absolute_uri()).hostname  # Obtiene solo el dominio base
            
            if Domain.objects.filter(domain=f'{instance.schema_name}.{base_domain}').exists():
                messages.error(request, 'El dominio ya existe. Elige un nombre diferente para el cliente.')
                return redirect('client_register')
            else:
                try:
                    subdomain_name = clean_domain_name(client_name)
                    domain = Domain.objects.create(
                        domain=f'{subdomain_name}.{base_domain}',
                        tenant=instance,
                        is_primary=True
                    )
                except Exception as e:
                    messages.error(request, f'Error al crear el cliente: {e}')
                    return redirect('client_register')

            messages.success(request, f'El cliente "{client_name}" ha sido creado exitosamente.')
            return redirect('home')
            
        else:
            messages.warning(request, 'La creación del cliente ha tenido un problema.')
    else:
        form = ClientRegisterForm()

    context = {
        'form': form,
        'title': 'Registrar Cliente',
        'Action': 'create',
    }

    return render(request, 'client_register.html', context)


def set_language(request):
    """Simple view para cambiar el idioma de la sesión y cookie.

    Espera un POST con `language` (ej: 'en' o 'es'). Redirige a `next` o a la página anterior.
    """
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    lang_code = request.POST.get('language') or request.GET.get('language')

    # seguridad básica para redirecciones
    try:
        # Django <4 used is_safe_url; use same check via allowed hosts
        from django.utils.http import url_has_allowed_host_and_scheme
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = '/'
    except Exception:
        pass

    if lang_code and lang_code in dict(getattr(settings, 'LANGUAGES', [])):
        session_key = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
        request.session[session_key] = lang_code
        translation.activate(lang_code)
        response = HttpResponseRedirect(next_url)
        response.set_cookie(getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language'), lang_code)
        return response

    return HttpResponseRedirect(next_url)
