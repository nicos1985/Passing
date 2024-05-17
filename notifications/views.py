from django.contrib import messages
from django.db.models.query import QuerySet
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from login.models import CustomUser
from notifications.forms import CreateNotificationForm
from notifications.models import AdminNotification, UserNotifications
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import user_passes_test

from passbase.models import Contrasena
from permission.models import ContraPermission

#devuelve si es administrador
def is_administrator(user):
    return user.is_superuser

# Create your views here.
class CreateNotificationsUser():
    pass

@user_passes_test(is_administrator)
def share_contrasena_form(request, contrasena):
    if request.method == 'POST':
        # Procesa el formulario si es una solicitud POST
        form = CreateNotificationForm(request.POST)
        if form.is_valid():
            # Si el formulario es válido, procesa los datos y guarda en el modelo UserNotifications
            share = form.cleaned_data['id_user_share']
            comment = form.cleaned_data['comment']
            contrasena_obj = Contrasena.objects.get(id=contrasena)
            
            # Crea una instancia de AdminNotifications y guarda los datos en la base de datos
            notificacion, created = AdminNotification.objects.get_or_create(
                id_contrasena=contrasena_obj,
                id_user_share=share, 
                defaults={
                    'id_user': request.user.username, 
                    'type_notification': 'Compartir Contraseña', 
                    'action': 'Permiso a contraseña',
                    'comment': comment,
                    'viewed': False,
                }
            )
            if created:
                message = f'Se ha solicitado compartir la contraseña "{contrasena_obj.nombre_contra}" con el usuario {share}.'
                messages.success(request, message)
            else:
                message = f'Ya existe una solicitud para compartir la contraseña "{contrasena_obj.nombre_contra}" con el usuario {share}. Si no fue atendida la solicitud comuníquese con el administrador'
                messages.warning(request, message)

            # Redirige a una página de éxito o a donde sea necesario
            return redirect('listpass')
        else:
            # Muestra los errores del formulario
            messages.error(request, 'Hay errores en el formulario, por favor verifica los campos.')
    else:
        # Si no es una solicitud POST, simplemente muestra el formulario vacío
        form = CreateNotificationForm()

    return render(request, 'create-noti-admin.html', {'form': form})



class ListNotificationsUser():
    pass


class ListNotificationsAdmin(LoginRequiredMixin, ListView):
    model = AdminNotification
    template_name = 'admin-noti-list.html'
    context_object_name = 'notifications'
    login_url = 'login'
    ordering = ['viewed', '-created']
    

class UpdateNotificationsUser():
    pass

class UpdateNotificationsAdmin():
    pass

