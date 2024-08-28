
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import SetPasswordForm
from .forms import CustomLoginForm, UserDepartureForm, UserRegisterForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from .models import CustomUser
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, UpdateView
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator


# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#####################################




# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)

        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            messages.success(request, f'El usuario {username} ha sido creado exitosamente')
            return redirect('listpass')
        else:
            messages.warning(request, 'La creacion de usuario ha tenido un problema.')

    else:
        form = UserRegisterForm()
        
    context = { 
        'form' : form,
        'title': 'Registrarse',
        'Action': 'create',
    }

    return render(request, 'register.html', context)



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