from django.shortcuts import render
from django.core.mail import send_mail
from django.http import HttpResponse
from django.views import View
from .config import EMAIL_SETTINGS
from .forms import EmailConfigForm
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator

# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#######################################

def home(request):
    return render(request, 'home.html')

def config(request):
    return render(request, 'admin.html')

@user_passes_test(is_superadmin)
def test_send_email(request):
    subject = 'Prueba de envío de correo'
    message = 'Este es un correo electrónico de prueba'
    from_email = 'nicolas.ferratto@previ.com.ar'
    recipient_list = ['nicolasferratto@hotmail.com']

    send_mail(subject, message, from_email, recipient_list, fail_silently=False)

    print('Correo electrónico enviado')
    return render(request, 'test_send_email.html')



@method_decorator(user_passes_test(is_superadmin), name='dispatch')
class UpdateEmailConfigView(View):

    def get(self, request):
        form = EmailConfigForm()
        return render(request, 'email_config.html', {'form': form})
    
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

            return render(request, 'email_config.html', {'message':'El formulario se envió correctamente', 'form':form, })
        else:
            return render(request, 'email_config.html', {'message':'El formulario no se envió correctamente'})