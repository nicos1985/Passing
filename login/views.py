from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import SetPasswordForm
from client.models import Client
from permission.models import PermissionRoles
from .forms import CustomLoginForm, GlobalSettingsForm, SuperUserRegisterForm, UserDepartureForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import CustomUser, GlobalSettings, MultifactorChoices
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, UpdateView
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
import json
from django.utils.html import escape
import pyotp
import qrcode
from io import BytesIO
from django.contrib.auth import login
from passing.config import EMAIL_SETTINGS
from django.core.mail import EmailMessage
from django.utils.html import format_html
from email.mime.image import MIMEImage


# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#####################################

# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False
            
                username = form.cleaned_data['username']
                user.client = Client.objects.get(schema_name=request.tenant.schema_name)
                user.save()
            except Exception as e:
                messages.warning(request, 'La creacion de usuario ha tenido un problema save. error: {e}')

            try:
                # Generar token de activación
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))

                # Construir la URL de activación
                activation_url = f"http://{request.get_host()}/login/reset-password/confirm/{uid}/{token}/" #prestar atencion cuando pase a https
            except Exception as e:
                messages.warning(request, 'La creacion de usuario ha tenido un problema token. error: {e}')

            # Enviar correo electrónico
            subject = 'Activa tu cuenta de usuario'
            message = render_to_string('activation_email.html', {
                'user': user,
                'activation_url': activation_url,
            })

            try:
                send_mail(subject, message, 'noreply@anima.bot', [user.email])
            except Exception as e:
                messages.warning(request, f'No se ha podido enviar el mail a {user.email}')

            messages.success(request, f'El usuario {username} ha sido creado exitosamente')
            return redirect('userlist')
        else:
            messages.warning(request, 'La creacion de usuario ha tenido un problema.')

    else:
        form = UserForm()
        
    context = { 
        'form' : form,
        'title': 'Registrarse',
        'Action': 'create',
    }

    return render(request, 'register.html', context)

def create_uid_token(request):
    pass



def create_superuser(request, schema_name):
    """Crea un super user la 1ra vez que se crea una cuenta. 
    Envia mail de validacion de mail. 
    """
    client = get_object_or_404(Client, schema_name=schema_name)
    
    #valida si hay rol inicial y si no, crea el rol inicial para asignarle al superuser
    try:
        role, created = PermissionRoles.objects.get_or_create(rol_name='Rol Inicial',
                                                            comment='Rol inicial',
                                                            is_active=True
                                                            )
        #reated.contrasenas.set([])
    except Exception as e:
            messages.error(request, f'Hubo un error al crear el usuario | error: {e}')
            return redirect('home')
    
    #Chequea si el flag de superuser creado esta en True.
    if client.created_superuser == 1:
        messages.warning(request, 'El usuario admin ya fue creado para este cliente.')
        return redirect('home')

    if request.method == 'POST':
        form = SuperUserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_superuser = True
            user.is_active = False  # El superusuario no estará activo hasta verificar el correo
            user.assigned_role = role
            user.client = client
            user.save()
            
            #Crear Settings Globales
            try:
                global_settings = GlobalSettings.objects.create()
            except Exception as e:
                messages.warning(request, f'No se ha podido crear las Configuraciones Globales')
                context['action'] = 'Error en Configuraciones globales'
                return render(request, 'client_register.html', context)
            

            # Generar token de activación
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            

            # Construir la URL de activación
            activation_url = f"http://{request.get_host()}/login/activate/{uid}/{token}/" #prestar atencion cuando pase a https

            # Enviar correo electrónico
            subject = 'Activa tu cuenta de usuario admin'
            message_html = render_to_string('activation_email.html', {
                'user': user,
                'activation_url': activation_url,
            })
            message = escape(json.dumps(message_html)) #lo paso a json para que no escape el html en la vista
            mail_from= EMAIL_SETTINGS['DEFAULT_FROM_EMAIL']
            context={'subject':subject,
                         'message':message,
                          'mail_from': mail_from,
                          'email':user.email,
                          'action':''}
            try:
                send_mail(subject, message='', from_email=mail_from, recipient_list=[user.email], html_message=message_html)
                
                context['action'] = '¿Recibiste el mail de verificacion?'
                messages.success(request, 'El usuario admin ha sido creado. Revisa tu email para activarlo.')
                return render(request,'recive-mail.html',context=context)
            
            except Exception as e:
                messages.warning(request, f'No se ha podido enviar el mail a {user.email}')
                context['action'] = 'Error en el envío de mail.'
                return render(request,'recive-mail.html',context=context) 
            
            
    else:
        form = SuperUserRegisterForm()

    context = {
        'form': form,
        'title': 'Crear usuario admin',
        'Action': 'create',
    }

    return render(request, 'register.html', context)

User = get_user_model()

def resend_mail(request):
    """Reenvia el mail en caso de que no lo haya recibido. Se dispara al presionar el boton de reenviar"""
    if request.method=='POST':
        subject = request.POST.get('subject')
        message_json = request.POST.get('message')
        mail_from = request.POST.get('mail_from')
        email = request.POST.get('email')
        action = request.POST.get('action')

        message_html = json.loads(message_json)
        context={'subject':subject,
                         'message': message_json,
                          'mail_from': mail_from,
                          'email': email,
                          'action': action}
        try:
            send_mail(subject, message='', from_email=mail_from, recipient_list=[email], html_message=message_html)
            
            messages.success(request, f'Se ha enviado el mail correctamente a {email}')
            context['action'] = '¿Recibiste el mail de verificacion?'
            return render(request,'recive-mail.html',context=context)
        
        except Exception as e:

            messages.error(request, f'Se ha producido un error al enviar el mail {e}')
            return render(request,'recive-mail.html',context=context) 
        
    return HttpResponse("Método no permitido", status=405)

def recive_mail(request):
    """Pregunta la recepcion de mail. En caso de no haberlo recibido da la opcion de reenviarlo."""
    if request.method=='GET':
        return render(request, 'recive-mail.html')


def activate_superuser(request, uidb64, token):
    """Activa el superuser cuando recibe el token correcto."""
    
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        
        
        client = Client.objects.filter(id=user.client.id).first()
        if client:
            client.created_superuser = 1
            client.save()
        messages.success(request, 'Tu cuenta ha sido activada exitosamente.')
        return redirect('login')
    else:
        messages.error(request, 'El enlace de activación es inválido o ha expirado.')
        return redirect('home')



class LoginFormView(LoginView):
    form_class = CustomLoginForm
    template_name = 'login.html'
    

    def get_context_data(self, **kwargs):
          
        context = super().get_context_data(**kwargs)
        context['title'] = 'Login'
        context['entity'] = 'Ingreso'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'login'

        return context
    
    def form_invalid(self, form):
        """If the form is invalid, render the invalid form with error messages."""
        messages.error(self.request, "Nombre de usuario o contraseña incorrectos.")
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """If the form is valid, check for 2FA and handle redirection."""
        user = form.get_user()

        if user.is_2fa_enabled:
            # Inicia sesión pero redirige a 2FA
            login(self.request, user)  # Establece la sesión del usuario
            self.request.session['is_2fa_verified'] = False  # Asegurarse de que no esté verificado
            self.request.session['2fa_user_id'] = user.id  # Guardar el ID del usuario para 2FA
            messages.info(self.request, "Por favor, verifica tu código de autenticación.")
            return redirect('verify_2fa')  # Redirige a la vista de verificación 2FA

        # Si no tiene 2FA habilitado, proceder normalmente
        messages.success(self.request, f"Inicio de sesión exitoso. Bienvenido {user.username}.")
        return super().form_valid(form)
    


class LogoutFormView(LogoutView):
    template_name = 'logout.html'

    def get_context_data(self, **kwargs):
          
          context = super().get_context_data(**kwargs)
          context['title'] = 'Logout'
          context['entity'] = 'Salida'
          context['list_url'] = reverse_lazy('login')
          context['action'] = 'logout'
            
          return context

        
@login_required
def profile_view(request):
    user = CustomUser.objects.get(id=request.user.id)
    if request.method == 'POST': 
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        if profile_form.is_valid():
            if profile_form.is_bound:
                is_2fa_enabled = profile_form.cleaned_data['is_2fa_enabled']
                if profile_form.initial['is_2fa_enabled'] == True:
                    if is_2fa_enabled == False:
                        disable_2fa(request)
                else:
                    qr_generate = is_2fa_enabled == True and user.otp_secret is None
                    if qr_generate:
                        profile_form.save()
                        return render(request, 'generate-qr-code.html')
                    else:
                        profile_form.save()
                        return render(request, 'listpass.html')
        else:
            print('Formulario no válido')
        
    else:
        profile_form = ProfileForm(instance=user)
        
        context = {
            'user_profile': user,
            'profile_form': profile_form,
            'has_otp_secret': user.has_otp_secret(),
        }
            
        return render(request, 'profile.html', context)
    return render(request, 'listpass.html')


class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = 'password_reset.html'
    success_message = "Se ha enviado un correo electrónico con instrucciones para restablecer la contraseña."


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'  # Cambia esto a la plantilla que estás utilizando
    form_class = SetPasswordForm  # Especifica el formulario que deseas utilizar

    def form_valid(self, form):
        # Guardar la nueva contraseña
        user = form.save()

        # Activar al usuario si no está activo
        if not user.is_active:
            
            user.is_active = True
            user.save()
            messages.success(self.request, "Tu cuenta ha sido activada con éxito.")

        # Llamar al comportamiento predeterminado del form_valid
        return super().form_valid(form)

@method_decorator(user_passes_test(is_administrator), name='dispatch') 
class UserListView(ListView):   
    model = CustomUser
    template_name = 'user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        obj = CustomUser.objects.all().order_by('is_active')
        
        return obj
    
@method_decorator(user_passes_test(is_administrator), name='dispatch') 
class UserUpdateView(UpdateView):
    model = CustomUser
    form_class = UserForm
    template_name = 'user_form.html'
    success_url = reverse_lazy('userlist')
    #print(f'now: {date.today()}')

   
    def get_initial(self):
            initial = super().get_initial()
            initial['birth_date'] = self.object.formatted_birth_date()
            initial['admission_date'] = self.object.formatted_admission_date()
            initial['departure_date'] = self.object.formatted_departure_date()
            return initial

@method_decorator(user_passes_test(is_administrator), name='dispatch')     
class DepartureUser(UpdateView):
    model = CustomUser
    form_class = UserDepartureForm
    template_name = 'departure_user.html'
    success_url = reverse_lazy('userlist')  # Asegúrate de que 'userlist' sea el nombre correcto en urls.py

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.get_object()  # Agregamos el usuario al contexto
        return context

    def form_valid(self, form):
        try:
            user = self.get_object()
            print(f'estoy en form valid: user = {user}')  # Obtener el usuario actual basado en la pk de la URL
            deactivate = deactivate_user(self.request, user.id)
            print(f'deactivate return: {deactivate}')
            messages.success(self.request, f"Se dió de baja exitosamente al usuario {user.username}.")
        except Exception as e:
            print(f'exception departure_user: {e}')
            messages.error(self.request, f"Error al dar de baja al usuario: {str(e)}")
        return super().form_valid(form)


def deactivate_user(request, pk):
    try:
        user = get_object_or_404(CustomUser, pk=pk)
        print(f'user_deactivate = {user}')
        if user == request.user:
            messages.error(request, "No puedes eliminar el mismo usuario con el que estás logueado.")
            return redirect('userlist')
        
        superusers = CustomUser.objects.filter(is_superuser=True, is_active=True).count()
        if user.is_superuser and superusers <= 1:
            messages.error(request, f'No se puede eliminar al usuario {user.username} ya que es el único superusuario.')
        else:
            message = user.inactivate()
            
            messages.success(request, message)
        
    except CustomUser.DoesNotExist:
        messages.error(request, f"El usuario con ID {pk} no existe.")
    except Exception as e:
        messages.error(request, f"Error al desactivar el usuario: {str(e)}")

    return message

@user_passes_test(is_administrator)
def activate_user(request, pk):
    try:
        user = get_object_or_404(CustomUser, id=pk)

        message = user.activate()
        messages.success(request, message)
        
    except CustomUser.DoesNotExist:
        message = f"El usuario con ID <strong>{pk}</strong> no existe."
        messages.error(request, message)
    except Exception as e:
        message = f"Error al activar el usuario: {str(e)}"
        messages.error(request, message)

    return render(request, 'user_list.html', {'users': CustomUser.objects.all().order_by('is_active')})


def verify_2fa(request):
    if request.method == "POST":
        code = request.POST.get("otp_code")
        if request.user.otp_secret:
            totp = pyotp.TOTP(request.user.otp_secret)
            if totp.verify(code):
                # Marcar como verificado en la sesión
                request.session["is_2fa_verified"] = True
                return redirect("listpass")  # Redirige al área protegida
            else:
                messages.error(request, "Código inválido. Intenta nuevamente.")
        else:
            messages.error(request, "2FA no está configurado en tu cuenta.")
    return render(request, "verify_2fa.html")


def show_qr_code_2fa(request):
    """Muestra el código QR en la web como imagen."""
    user = request.user
    qr_buffer = generate_qr_bytes(user)  

    return HttpResponse(qr_buffer, content_type="image/png")

def generate_qr_bytes(user):
    """Genera un código QR en bytes para un usuario específico."""
    if not user.otp_secret:
        secret = user.otp_secret = pyotp.random_base32()  # Genera un secret si no lo tiene
        user.save()
    else:
        secret = user.otp_secret

    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        user.username,
        issuer_name="Passing"
    )

    qr = qrcode.make(totp_uri)  # Genera el código QR
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0) 

    return buffer  # Devuelve los bytes de la imagen

import base64

def generate_qr_base64(user):
    """Genera un código QR y lo devuelve como una cadena Base64."""
    qr_buffer = generate_qr_bytes(user)  # Reutilizamos la función anterior

    # Convertir la imagen a Base64
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')
    image_data = base64.b64decode(qr_base64)  # Decodificar Base64

    # Guardar la imagen en un archivo
    #with open("qr_code_test.png", "wb") as f:
        #f.write(image_data)
    return qr_base64  # Devuelve la cadena Base64

def disable_2fa(request):
    """
    Deshabilita el 2fa para el usuario en particular.
    """
    if request.method == "POST" and request.user.is_authenticated:
        request.user.is_2fa_enabled = False
        request.user.otp_secret = None
        request.user.save()
        messages.success(request, "2FA ha sido desactivado.")
    return redirect("profile")

def disable_2fa_user(user):
    """
    Deshabilita el 2fa para el usuario en particular.
    """
    user.is_2fa_enabled = False
    user.otp_secret = None
    user.save()
        
    


def send_qr_code_email_inline(user):
        """Envía el código QR incrustado en el cuerpo del email."""
        
        qr_base64 = generate_qr_base64(user)  # Obtener QR en Base64
        
        # Crear el cuerpo del email con la imagen incrustada
        html_content = format_html(
            """
            <html>
                <body>
                    <p>Hola <b>{}</b>,</p>
                    <p>Escanea este código QR para configurar la autenticación en dos pasos en la aplicación Passing:</p>
                    <p>Escanea el código QR con "Google Authenticator"  <a href="https://play.google.com/store/search?q=google+authenticator&c=apps&hl=es_419" target="_blank">Descargalo aqui</a></p>
                    <img src="data:image/png;base64,{}" alt="QR Code" style="width:200px; height:200px;">
                    <p>Si tienes problemas, contáctanos.</p>
                    <p>Atentamente, <br><b>El equipo de Passing</b></p>
                </body>
            </html>
            """,
            user.username, qr_base64
        )
        print(f'message_email {html_content}')
        # Crear el email con formato HTML
        email = EmailMessage(
            subject="Tu Código QR para Autenticación en Passing",
            body=html_content,
            from_email="noreply@anima.bot",
            to=[user.email]
        )

        email.content_subtype = "html"  # Especificar que el contenido es HTML

        # Enviar el email
        email.send()

def send_qr_code_email_cid(user):
    """Envía el código QR como imagen embebida en el correo (CID)."""
    qr_buffer = generate_qr_bytes(user)  # Genera la imagen en bytes

    # Crear el email con HTML y referenciar la imagen con CID
    subject = "Tu Código QR para Autenticación en Passing"
    message = """
    <html>
        <body>
            <p>Hola <b>{}</b>,</p>
            <p>Escanea este código QR para configurar la autenticación en dos pasos en la aplicación Passing:</p>
            <p>Escanea el código QR con "Google Authenticator"  <a href="https://play.google.com/store/search?q=google+authenticator&c=apps&hl=es_419" target="_blank">Descargalo aqui</a></p>
            <img src="cid:qrcode" alt="QR Code" style="width:200px; height:200px;">
            <p>Si tienes problemas, contáctanos.</p>
            <p>Atentamente, <br><b>El equipo de Passing</b></p>
        </body>
    </html>
    """.format(user.username)

    email = EmailMessage(subject, message, 'noreply@anima.bot', [user.email])
    email.content_subtype = "html"  # Importante para permitir HTML en el email

    # Crear la imagen como un archivo adjunto embebido
    image = MIMEImage(qr_buffer.getvalue(), _subtype="png")
    image.add_header('Content-ID', '<qrcode>')  # CID que se usa en el <img>
    image.add_header('Content-Disposition', 'inline', filename="qrcode.png")
    email.attach(image)  # Adjuntar la imagen al email

    email.send()
    
def send_qr_email_for_user_ondemand(request, pk):
    user = CustomUser.objects.get(id=pk)
    try:
        send_qr_code_email_cid(user)
        messages.success(request, f"El código QR a {user} se ha enviado correctamente al correo {user.email}.")
    except Exception as e:
        messages.warning(request, f'El mail no ha podido enviarse a {user.email}. ERROR: {e}')

    return redirect('userlist')


class GlobalSettingsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista para update las configuraciones globales a nivel de cuenta.
    """
    model = GlobalSettings
    template_name = 'global_settings.html'
    form_class = GlobalSettingsForm
    success_url = reverse_lazy('config')

    def test_func(self):
        return is_administrator(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a Configuraciones Globales")
        return redirect('listpass')  # Redirigir a la página de inicio u otra página adecuada

    def get_queryset(self):
        
        return super().get_queryset()
    
    
    
    def form_valid(self, form):
        """Intercepta la validación antes de guardar"""
        instance = form.save(commit=False)  # Obtiene el objeto sin guardarlo aún

        if instance.multifactor_status == MultifactorChoices.ACTIVADO:
            # Ejecuta una función si el campo `multifactor_status` está activado
            print(f'pasa por activado')
            self.activate_multifactor_for_all()
        elif instance.multifactor_status == MultifactorChoices.DESACTIVADO:
            print(f'pasa por desactivado')
            self.deactivate_multifactor_for_all()

        instance.save()  # Guarda el objeto en la base de datos
        form.save_m2m()  # Guarda las relaciones ManyToMany si existen

        return super().form_valid(form)
    

    def activate_multifactor_for_all(self):
        """
        Activa todos los factores multiples de autenticacion a todos los usuarios. 
        Envia mail a cada uno con el QR para la activacion del mismo. 
        """
        users = CustomUser.objects.filter(is_active=True)
        

        for user in users:
            
            if user.is_2fa_enabled:
                pass
            else:
                user.is_2fa_enabled = True
                user.save()
                send_qr_code_email_cid(user)


    def deactivate_multifactor_for_all(self):
        """desactiva todos los factores multiples de autenticacion a todos los usuarios."""
        users = CustomUser.objects.filter(is_active=True)
        
        for user in users:
            if user.has_otp_secret:
                disable_2fa_user(user)



    