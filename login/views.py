from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import login
from .forms import CustomLoginForm, UserRegisterForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from django.forms import forms
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, UpdateView





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

        user = CustomUser.objects.get(username=username)
        if request.method == 'POST':
            print('pasando por post')
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
    return render(request, 'login.html')



class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = 'password_reset.html'
    success_message = "Se ha enviado un correo electrónico con instrucciones para restablecer la contraseña."
    
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'  # Cambia esto a la plantilla que estás utilizando
    form_class = SetPasswordForm  # Especifica el formulario que deseas utilizar

class UserListView(ListView):   
    model = CustomUser
    template_name = 'user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        obj = CustomUser.objects.all().order_by('is_active')
        print(f'obj_user: {obj}')
        return obj
    

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
    

def deactivate_user(request, pk):
    try:
        user = get_object_or_404(CustomUser, id=pk)
        if user == request.user:
            message = f"No podes eliminar el mismo usuario con el que estás logueado."
            messages.error(request, message)
            print(messages.error(request, message))
            return redirect('userlist')
        superusers = CustomUser.objects.filter(is_superuser=True, is_active=True).count()
        
        print(f'count superuser: {superusers}')

        if user.is_superuser:
            if superusers > 1:
                message = user.inactivate()
                messages.success(request, message)
            else:
                message = f'No se puede eliminar el usuario <strong>{user.username}</strong> ya que es el único superusuario en el listado de usuarios'
                messages.error(request, message)
        else:
            message = user.inactivate()
            messages.success(request, message)
        
    except CustomUser.DoesNotExist:
        message = f"El usuario con ID <strong>{pk}</strong> no existe."
        messages.error(request, message)
    except Exception as e:
        message = f"Error al desactivar el usuario: {str(e)}"
        messages.error(request, message)

    return render(request, 'user_list.html', {'users': CustomUser.objects.all().order_by('is_active')})

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