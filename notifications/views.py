from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from login.models import CustomUser
from notifications.forms import CreateNotificationForm
from notifications.models import AdminNotification, UserNotifications
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

from passbase.models import Contrasena


# Create your views here.
class CreateNotificationsUser():
    pass


def share_contrasena_form(request, contrasena):
    contraseña = contrasena

    if request.method == 'POST':
        # Si es una solicitud POST, procesa el formulario
        form = CreateNotificationForm(request.POST)
        if form.is_valid():
            # Si el formulario es válido, procesa los datos y guarda en el modelo UserNotifications
            share = form.cleaned_data['id_user_share']
            comment = form.cleaned_data['comment']

            # Crea una instancia de AdminNotifications y guarda los datos en la base de datos
            notificacion = AdminNotification(
                id_contrasena=Contrasena.objects.get(id=contraseña),
                id_user=request.user.username,  # Suponiendo que id_user es el ID del usuario actual
                id_user_share= share,  # Ajusta según tu lógica de negocio
                type_notification= 'Compartir Contraseña',
                action = 'Permiso a contraseña',  # Ajusta según tu lógica de negocio
                comment=comment,
                viewed = False
            )
            notificacion.save()

            # Redirige a una página de éxito o a donde sea necesario
            return redirect('listpass')
        else:
            print(form.errors)
            
    else:
        # Si no es una solicitud POST, simplemente muestra el formulario vacío
        form = CreateNotificationForm()

    return render(request, 'create-noti-admin.html', {'form': form})



class ListNotificationsUser():
    pass

class ListNotificationsAdmin():
    pass

class UpdateNotificationsUser():
    pass

class UpdateNotificationsAdmin():
    pass
