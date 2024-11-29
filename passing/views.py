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