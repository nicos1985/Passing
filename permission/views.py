from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django import forms
from django.urls import reverse
from django.contrib import messages
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, FormView

from notifications.models import AdminNotification
from .models import ContraPermission
from passbase.models import Contrasena
from .forms import PermissionUserForm, PermisoForm
from login.models import CustomUser
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

#devuelve si es administrador
def is_administrator(user):
    return user.is_superuser



@method_decorator(user_passes_test(is_administrator), name='dispatch') #no permite ingreso si no es superuser
class PermissionListView(LoginRequiredMixin, ListView):
    model = ContraPermission
    template_name = 'listpermission.html'
    login_url = '/login/login/'
     

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Permisos'
        return context
    
    def get_queryset(self):
        permisos =  ContraPermission.objects.all().order_by('-user_id', '-contra_id__seccion')
       
        return permisos
    


@user_passes_test(is_administrator)
def seleccionar_usuario(request):
    usuario_form = PermissionUserForm()
    print(f'usuario_form no post: {usuario_form}')
    if request.method == 'POST':
        usuario_form = PermissionUserForm(request.POST)
        print(f'usuario_form post: {usuario_form}')
        if usuario_form.is_valid():
            print(f'formulario userform es valido')
            usuario = usuario_form.cleaned_data['usuario']
            print(f'usuario = {usuario}')
            # Redirige a la vista de permisos y pasa el usuario
            return redirect('permissionform2', usuario_id=usuario.id)

    return render(request, 'create-perm-p1.html', {'usuario_form': usuario_form})

@user_passes_test(is_administrator)
def gestion_permisos(request, usuario_id):
    print(f'usuario_id (gestion permisos): {usuario_id} ')
    usuario = get_object_or_404(CustomUser, id=usuario_id)
    print(f'usuario (gestion permisos): {usuario} ')
    permiso_form = PermisoForm(usuario, request.POST or None)
    contrasena = Contrasena.objects.all()
    if request.method == 'POST':
        if permiso_form.is_valid():
            # Procesa el formulario de permisos y guarda los cambios
            
            for contraseña in contrasena:
                default_value = False
                permiso = permiso_form.cleaned_data.get(f'permiso_{contraseña.nombre_contra}', default_value)

                permissions, _ = ContraPermission.objects.get_or_create(
                    user_id=usuario,
                    contra_id=contraseña
                )
                print(f'permissions: {permissions}')
                permissions.permission = permiso
                print(f'permissions.permission: {permissions.permission}')
                permissions.save()

            # Redirige a donde desees después de guardar los cambios
            messages.success(request,  'los permisos han sido asignados correctamente.')
            
            return redirect('listpass')
    else:
        for contra in contrasena:
            print(f'contraseñas: {contra.usuario}')
        return render(request, 'create-perm-p2.html', {
            'permiso_form': permiso_form,
            'usuario' : usuario,
            'contraseñas' : contrasena,
        })
        

def grant_permission(request, id_cont, id_user_share, id_noti):
    try:
        # Obtener o crear el objeto de permiso
        notificacion = get_object_or_404(AdminNotification, id=id_noti)
        contrasena = get_object_or_404(Contrasena, id=id_cont)
        user_share = get_object_or_404(CustomUser, id=id_user_share)
        permission_obj, created = ContraPermission.objects.get_or_create(
            user_id=user_share, 
            contra_id=contrasena,
            defaults={'permission': True, 'perm_active': True}
        )
        
        # Si el objeto ya existía, actualizar el campo 'permission'
        if not created:
            permission_obj.permission = True
            permission_obj.save()  # Guardar los cambios en la base de datos
        notificacion.viewed = True
        notificacion.save()
        message = f'Permisos sobre {contrasena.nombre_contra} otorgados a {user_share.username}.'
        messages.success(request, message)

    except Exception as e:
        messages.error(request, f'Hubo un error al otorgar permisos: {e}')
    # Redirigir a la vista 'notificaciones'
    return redirect('listnotifadmin')