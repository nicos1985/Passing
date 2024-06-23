from django.contrib import messages
from django.db.models.query import QuerySet
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from login.models import CustomUser
from notifications.forms import CreateNotificationForm
from notifications.models import AdminNotification, UserNotifications
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from passbase.models import Contrasena
from permission.models import ContraPermission

def can_view_contrasena(user, request):
    contrasena_id = int(request.GET.get('contrasena'))
    contrasena_obj = get_object_or_404(Contrasena, id=contrasena_id)
    return user.is_staff or ContraPermission.objects.filter(user_id=user, contra_id=contrasena_obj, permission=True).exists()

def is_administrator(user):
    return user.is_superuser or user.is_staff

@login_required
def share_contrasena_form(request, contrasena):
    if request.method == 'POST':
        form = CreateNotificationForm(request.POST)
        if form.is_valid():
            share = form.cleaned_data['id_user_share']
            comment = form.cleaned_data['comment']
            contrasena_obj = get_object_or_404(Contrasena, id=contrasena)

            obj_permission = ContraPermission.objects.filter(user_id=share, contra_id=contrasena, permission=True).first()
            if not obj_permission:
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
                    message = f'Ya existe una solicitud para compartir la contraseña "{contrasena_obj.nombre_contra}" con el usuario {share}. Si no fue atendida la solicitud comuníquese con el administrador.'
                    messages.warning(request, message)
            else:
                message = f'El usuario {share} ya puede visualizar la contraseña "{contrasena_obj.nombre_contra}".'
                messages.success(request, message)
            
            return redirect('listpass')
        else:
            messages.error(request, 'Hay errores en el formulario, por favor verifica los campos.')
    else:
        form = CreateNotificationForm()
    
    return render(request, 'create-noti-admin.html', {'form': form})

class ListNotificationsUser(LoginRequiredMixin, ListView):
    model =UserNotifications
    template_name = 'user-noti-list.html'
    context_object_name = 'notifications'
    login_url = 'login'
    
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = UserNotifications.objects.filter(id_user=self.request.user).order_by('viewed', '-created')  # Ajusta 'campo' según tu modelo

        return queryset

    
class MarkNotificationsViewed(LoginRequiredMixin, View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if not request.user.is_authenticated:
                return HttpResponseForbidden("No autorizado")
            notifications = UserNotifications.objects.filter(id_user=request.user)
            for noti in notifications:
                noti.viewed = True
                noti.save()
            return JsonResponse({'status': 'success'})
        return HttpResponseForbidden("No autorizado")    

class ListNotificationsAdmin(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AdminNotification
    template_name = 'admin-noti-list.html'
    context_object_name = 'notifications'
    login_url = 'login'
    ordering = ['viewed', '-created']

    def test_func(self):
        return is_administrator(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta página.")
        return redirect('listpass')  # Redirigir a la página de inicio u otra página adecuada

class UpdateNotificationsUser():
    pass

class UpdateNotificationsAdmin():
    pass

