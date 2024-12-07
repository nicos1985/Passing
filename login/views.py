
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import SetPasswordForm
from client.models import Client
from permission.models import PermissionRoles
from .forms import CustomLoginForm, SuperUserRegisterForm, UserDepartureForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from .models import CustomUser
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
from passing.config import EMAIL_SETTINGS


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
        """If the form is valid, redirect to the success URL with a success message."""
        messages.success(self.request, f"Inicio de sesión exitoso. Bienvenido {form.cleaned_data['username']}.")
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
def profile_view(request, username):
    if username is not None:
        if username == request.user.username:
            user = CustomUser.objects.get(username=username)
            if request.method == 'POST':
                
                profile_form = ProfileForm(request.POST, request.FILES, instance=user)
                if profile_form.is_valid():
                    profile_form.save()
                else:
                    print('Formulario no válido')
                
            else:
                profile_form = ProfileForm(instance=user)

            context = {
                'user_profile': user,
                'profile_form': profile_form,
            }

            return render(request, 'profile.html', context)
        else:
            messages.error(request, "No tenes permisos para ingresar a este perfil")
            return redirect(reverse('listpass'))
    return render(request, 'login.html')



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