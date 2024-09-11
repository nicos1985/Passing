from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django import forms
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, FormView

from notifications.models import AdminNotification, UserNotifications
from .models import ContraPermission, PermissionRoles
from passbase.models import Contrasena, LogData
from .forms import PermissionRolesForm, PermissionUserForm, PermisoForm, UserRolForm
from login.models import CustomUser
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

#devuelve si es administrador
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser



@method_decorator(user_passes_test(is_administrator), name='dispatch') #no permite ingreso si no es superuser o es staff
class PermissionListView(LoginRequiredMixin, ListView):
    model = ContraPermission
    template_name = 'listpermission.html'
    login_url = '/login/login/'

    def get_queryset(self):
        permisos = ContraPermission.objects.filter(contra_id__is_personal=False).select_related('user_id', 'contra_id__seccion', 'contra_id__owner').order_by('-user_id', '-contra_id__seccion')
    
        return permisos
    


@user_passes_test(is_superadmin)
def seleccionar_usuario(request):
    usuario_form = PermissionUserForm()
    print(f'usuario_form no post: {usuario_form}')
    if request.method == 'POST':
        usuario_form = PermissionUserForm(request.POST)
        print(f'usuario_form post: {usuario_form}')
        if usuario_form.is_valid():
            print('formulario userform es valido')
            usuario = usuario_form.cleaned_data['usuario']
            print(f'usuario = {usuario}')
            # Redirige a la vista de permisos y pasa el usuario
            return redirect('permissionform2', usuario_id=usuario.id)

    return render(request, 'create-perm-p1.html', {'usuario_form': usuario_form})

@user_passes_test(is_superadmin)
def gestion_permisos(request, usuario_id):
    usuario = get_object_or_404(CustomUser, id=usuario_id)
    permiso_form = PermisoForm(usuario, request.POST or None)
    contrasena = Contrasena.objects.filter(is_personal=False)
    if request.method == 'POST':
        if permiso_form.is_valid():
            # Procesa el formulario de permisos y guarda los cambios
            
            for contrasena in contrasena:
                default_value = False
                permiso = permiso_form.cleaned_data.get(f'permiso_{contrasena.nombre_contra}', default_value)

                permissions, _ = ContraPermission.objects.get_or_create(
                    user_id=usuario,
                    contra_id=contrasena
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
        
@user_passes_test(is_administrator)
def grant_permission(request, id_cont, id_user_share, id_noti, id_user):
    try:
        # Obtener o crear el objeto de permiso
        user = get_object_or_404(CustomUser, username = id_user)
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
        user_notification_share = UserNotifications.objects.create(
                                                            id_contrasena = contrasena,
                                                            id_user = user_share,
                                                            type_notification = f"recibiste acceso a {contrasena.nombre_contra}",
                                                            comment = "Admin te dió acceso."
        )
        print(f'user_notificarions_share: {user_notification_share}')
        user_notification = UserNotifications.objects.create(
                                                            id_contrasena = contrasena,
                                                            id_user = user,
                                                            type_notification = "Permiso Concedido",
                                                            comment = f"Se dió acceso a {user_share.username}."
        )
        print(f'user_notification: {user_notification}')
        message = f'Permisos sobre {contrasena.nombre_contra} otorgados a {user_share.username}.'
        messages.success(request, message)

    except Exception as e:
        messages.error(request, f'Hubo un error al otorgar permisos: {e}')
    # Redirigir a la vista 'notificaciones'
    return redirect('listnotifadmin')

@method_decorator(user_passes_test(is_administrator), name='dispatch') #no permite ingreso si no es superuser
class PermissionRolesCreateView(CreateView):
    model = PermissionRoles
    form_class = PermissionRolesForm
    template_name = 'permission_roles_form.html'
    success_url = reverse_lazy('config')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añade las contraseñas al contexto
        context['contrasenas'] = Contrasena.objects.filter(is_personal=False)
        return context
# Funciones para la asignacion de Roles a usuarios. 

def give_permission(request, user, contrasena):
    try:
        permission=ContraPermission.objects.get_or_create(
                        user_id=user,
                        contra_id=contrasena, 
                        permission=True
                    )
        print(f'permissions: {permission}')
    except Exception as e:
        message = f'Hubo un error al intentar crear un permiso {contrasena}. Error {e}'
        messages.error(request, message)
    return True
    

def generate_rol_permissions(request, rol, user):
    rol = get_object_or_404(PermissionRoles, id=rol.id)
    usuario = get_object_or_404(CustomUser, id=user.id)
    contrasenas = rol.get_contrasenas() #obtengo todas las contraseñas relacionadas al Rol
    #intento eliminar todos los permisos actuales. 
    try:
        # Obtén el queryset de objetos que deben ser eliminados
        flush_permissions = ContraPermission.objects.filter(user_id=usuario)

        # Excluir aquellos que tienen una contraseña con is_personal=True
        flush_permissions = flush_permissions.exclude(contra_id__is_personal=True)

        # Eliminar los objetos que cumplen con los criterios
        flush_permissions.delete()
        
    except Exception as e:
        message = f'Hubo un error al intentar quitar los permisos existentes. Error {e}'
        messages.error(request, message)

    for contrasena in contrasenas:
        try:
            give_permission(request, usuario, contrasena)

        

        except Exception as e:
            message = f'hubo un error al dar permiso a la contraseña {contrasena}. Error {e}'
            messages.error(request, message)

    usuario.assigned_role = rol
    usuario.save()    

    return contrasenas

@user_passes_test(is_administrator)
def assign_rol_user(request, id_rol=None):
    """ Maneja el formulario donde se asignan los roles a los usuarios.
    Toma los datos y los pasa a la función generate_rol_permission """

    if request.method == "POST":
        # Crear formulario POST
        user_rol_form = UserRolForm(request.POST)
        if user_rol_form.is_valid():
            # Guardo el form
            user_rol_form.save()
            # Obtengo el usuario y el rol elegidos en el form para generar los permisos
            usuario = user_rol_form.cleaned_data['user']
            rol = user_rol_form.cleaned_data['rol']
            # Genero los permisos
            try:
                generate_rol_permissions(request, rol, usuario)
                message = f'Se ha otorgado el rol {rol} al usuario {usuario}'
                messages.success(request, message)
            except Exception as e:
                message = f'Hubo un error al ejecutar la asignación de permisos. Error: {e}'
                messages.error(request, message)

            return redirect('config')
        else:
            messages.error(request, 'Error en el formulario. Por favor, revise los datos ingresados.')
    else:
        # Crear Formulario GET
        if id_rol is not None:
            rol = get_object_or_404(PermissionRoles, id=id_rol)
            user_rol_form = UserRolForm(initial={'rol': rol})
        else:
            user_rol_form = UserRolForm()

    return render(request, 'assign_rol.html', {'form': user_rol_form})

@method_decorator(user_passes_test(is_administrator), name='dispatch')
class PermissionRolView(LoginRequiredMixin, ListView):
    model = PermissionRoles
    template_name = 'roles_list.html'
    context_object_name = 'roles'
    login_url = 'login'


    def get_queryset(self):
        queryset = PermissionRoles.objects.filter(is_active=True)
        for obj in queryset: 
            obj.related_count = obj.get_contrasenas().count()
           
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

@method_decorator(user_passes_test(is_administrator), name='dispatch')
class PermissionRolUpdate(LoginRequiredMixin, UpdateView):
    model = PermissionRoles
    form_class = PermissionRolesForm
    template_name = 'update_role.html'
    success_url = reverse_lazy('roles')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añade las contraseñas al contexto
        context['contrasenas'] = Contrasena.objects.filter(is_personal=False)
        return context

@method_decorator(user_passes_test(is_administrator), name='dispatch')
class ConfirmDeleteView(DeleteView):
    model = PermissionRoles
    template_name = 'delete_role.html'
    
   
    def get_success_url(self):
        return reverse_lazy('deleterolepk', kwargs={'pk': self.object.pk})

@user_passes_test(is_administrator)
def delete_rol(request, pk):
    
    delete_instance_role = get_object_or_404(PermissionRoles, id=pk)
    if delete_instance_role is not None:
        delete_instance_role.inactive()
        message = f'El Rol {delete_instance_role.rol_name} fué eliminado con éxito.'
        messages.success(request, message)
    else:
        message = 'Hubo un error buscar el rol.'
        messages.error(request, message)

    return render(request, 'roles_list.html', {'roles': PermissionRoles.objects.filter(is_active=True)})
    

@user_passes_test(is_administrator)
def update_owner(request):
    """Realizar la actualizacion del campo owner de cada contraseña. """
    contrasenas = Contrasena.objects.all()
    
    for contrasena in contrasenas:
        try:
            log_mod = LogData.objects.get(contraseña=contrasena.id, action='Create', entidad='Contraseña')
            print(f'log_mod: {log_mod}')

            contrasena.owner = log_mod.usuario
            contrasena.save()
            print(f'contrasena_owner_ok: {contrasena.owner}')

        except LogData.DoesNotExist:

            contrasena.owner = None
            contrasena.save()
            print(f'contrasena_owner_notexist: {contrasena.owner}')

    return render(request, 'listpass.html')
    

def users_audit(request):
    users = CustomUser.objects.filter(is_active=True)
    data = {'users': []}
    for user in users:
        user_role_assigned = user.assigned_role
        rol = PermissionRoles.objects.get(id=user_role_assigned.id)
    

        user_contrasenas_list = []
        contrasenas_of_role = rol.get_contrasenas()
        print(f'contrasenas_of_role: {contrasenas_of_role}')
        contrasenas_of_permission = ContraPermission.objects.filter(user_id=user)
        # Obtener la queryset del modelo Contrasena a partir de las relaciones en ContraPermission
        contrasenas_queryset = Contrasena.objects.filter(id__in=contrasenas_of_permission.values_list('contra_id', flat=True))
        print(f'contrasenas_queryset: {contrasenas_queryset}')
        contrasenas_diff = contrasenas_of_role.exclude(id__in=contrasenas_queryset.values_list('id', flat=True))
        print(f'contrasenas_diff {user}: {contrasenas_diff}')
        contrasenas_different = contrasenas_queryset.exclude(id__in=contrasenas_of_role.values_list('id', flat=True))
        print(f'contrasenas_different {user}: {contrasenas_different}')
        for contra in contrasenas_diff:
            user_contrasenas_list.append({
                'id': contra.id,
                'nombre_contra': contra.nombre_contra,
                'section': contra.seccion,
                'owner': contra.owner
            })

        data['users'].append({
            'user_id': user.id,
            'user_name': user.username,  # O cualquier otro campo que quieras mostrar del usuario
            'contrasenas': user_contrasenas_list
        })

    #print(f'context: {data}')

    return render(request, 'users_audit.html', context={'data': data})