from django.shortcuts import render
from django.core.mail import send_mail
from django.http import HttpResponse
from django.views import View
from .config import EMAIL_SETTINGS
from .forms import EmailConfigForm
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
import logging
# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#######################################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



TEMPLATE = 'email_config.html'

def home(request):
    return render(request, 'home.html')

def config(request):
    return render(request, 'admin.html')

#@user_passes_test(is_superadmin)
def test_send_email(request):
    subject = 'Prueba de envío de correo'
    message = 'Este es un correo electrónico de prueba'
    from_email = 'noreply@anima.bot'
    recipient_list = ['nicolasferratto@hotmail.com']

    log_messages = []  # Para guardar los mensajes que se mostrarán en pantalla

    try:
        logger.info('Iniciando el envío del correo.')
        log_messages.append('Iniciando el envío del correo.')

        logger.info(f'Asunto: {subject}')
        log_messages.append(f'Asunto: {subject}')

        logger.info(f'Mensaje: {message}')
        log_messages.append(f'Mensaje: {message}')

        logger.info(f'De: {from_email}')
        log_messages.append(f'De: {from_email}')

        logger.info(f'Para: {recipient_list}')
        log_messages.append(f'Para: {recipient_list}')

        # Intentar enviar el correo
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)

        logger.info('Correo electrónico enviado exitosamente.')
        log_messages.append('Correo electrónico enviado exitosamente.')

    except Exception as e:
        logger.error(f'Error al enviar el correo: {e}')
        log_messages.append(f'Error al enviar el correo: {e}')

    # Mostrar los logs en la página renderizada
    context = {
        'log_messages': log_messages
    }

    return render(request, 'test_send_email.html', context)




class UpdateEmailConfigView(View):

    def get(self, request):
        form = EmailConfigForm()
        return render(request, TEMPLATE, {'form': form})
    
    def post(self, request):
        form = EmailConfigForm(request.POST)
    
        if form.is_valid():

            additional_settings = {
            'SERVER_EMAIL': 'django@my-domain.example',
            'DEFAULT_FROM_EMAIL': form.cleaned_data['email_host_user'],
                }
            form_settings_uppercase = {key.upper(): value for key, value in form.cleaned_data.items()}

            EMAIL_SETTINGS.update(form_settings_uppercase)
            EMAIL_SETTINGS.update(additional_settings)


            with open('passing/config.py', 'w') as config_file:
                config_file.write(f"EMAIL_SETTINGS = {EMAIL_SETTINGS}\n")
            # Modifica las configuraciones según tus necesidades
            """
            EMAIL_SETTINGS['SERVER_EMAIL'] = 'django@my-domain.example'
            EMAIL_SETTINGS['DEFAULT_FROM_EMAIL'] = form.cleaned_data['email_host_user']
            EMAIL_SETTINGS['EMAIL_HOST'] = form.cleaned_data['email_host']
            EMAIL_SETTINGS['EMAIL_PORT'] = form.cleaned_data['email_port']
            EMAIL_SETTINGS['EMAIL_USE_TLS'] = form.cleaned_data['email_use_tls']
            EMAIL_SETTINGS['EMAIL_HOST_USER'] = form.cleaned_data['email_host_user']
            EMAIL_SETTINGS['EMAIL_HOST_PASSWORD'] = form.cleaned_data['email_host_password']
            """
            # Actualizar el diccionario en tiempo de ejecución
            

            for key, value in EMAIL_SETTINGS.items():
                print(f'{key}:{value}')

            return render(request, TEMPLATE, {'message':'El formulario se envió correctamente', 'form':form, })
        else:
            return render(request, TEMPLATE, {'message':'El formulario no se envió correctamente'})


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
            return redirect(f"http://{subdomain_name}.{base_domain}:8000/login/{instance.schema_name}/create-superuser/")
            
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