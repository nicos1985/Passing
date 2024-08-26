from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from cryptography.fernet import Fernet
from login.models import CustomUser
from notifications.models import UserNotifications
from passbase.crypto import decrypt_data, encrypt_data
from passing import settings
from .forms import ContrasenaForm, ContrasenaUForm, SectionForm
from .models import Contrasena, SeccionContra, LogData
from permission.models import ContraPermission
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test


def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser


class ContrasListView(LoginRequiredMixin, ListView):
    model = Contrasena
    template_name = 'listpass.html'
    context_object_name = 'query_perm'
    login_url = 'login'

    def get_queryset(self):
        log_data ={}
        fecha_hoy = timezone.now()
        # busco los objetos de permiso con el user logueado y extraigo los id de contraseña. 
        obj_permiso = ContraPermission.objects.filter(user_id = self.request.user, 
                                                    perm_active = True, 
                                                    permission = True).values_list('contra_id', flat=True)
        #convierto en lista
        permisos = list(obj_permiso)
        query_perm = Contrasena.objects.filter(active=True, id__in = permisos).order_by('seccion')

        # Desencriptar las contraseñas y añadirlas al queryset
        for item in query_perm:
            
            item.decrypted_password = item.get_decrypted_password()
            item.decrypted_user = item.get_decrypted_user()

        return query_perm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Contraseñas'

        
        return context


class ContrasDetailView(LoginRequiredMixin, DetailView):
    model=Contrasena
    template_name = 'detail-cont.html'
    login_url = 'login'

    def get(self, request, *args, **kwargs):
        # Verificar permisos antes de continuar
        users_permissions = ContraPermission.objects.filter(contra_id=self.kwargs['pk'], permission=True)
        print(f'users_permissions: {users_permissions}')
        lista_permision_user = [permision.user_id for permision in users_permissions]

        if request.user not in lista_permision_user:
            # Redirigir si no tiene permisos
            messages.error(request, 'No tienes permisos para ingresar a este detalle.')
            return redirect(reverse('listpass'))

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtén el objeto Contrasena y descifra los valores
        contraseña = self.get_object()
        contraseña.decrypted_password = contraseña.get_decrypted_password()
        
        contraseña.decrypted_user = contraseña.get_decrypted_user()

        log_data = LogData.objects.filter(contraseña=self.kwargs['pk']).order_by('-created')[:10]
        users_permissions = ContraPermission.objects.filter(contra_id=self.kwargs['pk'], permission=True)
        print(f'user permissions: {users_permissions}')

        for log in log_data:
            try:
                log.password = log.get_decrypted_password()
                encrypted_user = log.get_encrypted_user()

                if encrypted_user is not None:
                    decrypted_user = log.get_decrypted_user(encrypted_user)
                    log.detail = log.detail.replace(encrypted_user, decrypted_user)
            except Exception as e:
                print(f"Error processing log {log.id}: {e}")

        context['contraseña'] = contraseña
        context['log_data'] = log_data if log_data.exists() else None
        context['users_permissions'] = users_permissions

        return context
    
        

class ContrasCreateView(LoginRequiredMixin, CreateView):
    model = Contrasena, SeccionContra
    form_class = ContrasenaForm
    template_name = 'create-cont.html'
    success_url = reverse_lazy('listpass')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Contraseña'
        context['entity'] = 'Contraseñas'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'add'
        context['sections'] = SeccionContra.objects.filter(active=True)
        return context

    def form_valid(self, form, *args, **kwargs):
        cleaned_data = form.cleaned_data
        print(f'cleaned_Data: {cleaned_data}')
        cleaned_data['owner'] = self.request.user
        
        try:
            # Guarda el objeto usando form.save(commit=False) para no guardar inmediatamente
            contrasena = form.save(commit=False)
            contrasena.owner = self.request.user
            contraseña = cleaned_data.get('contraseña')

            if contraseña:
                contrasena.contraseña = encrypt_data(contraseña)
                contrasena.save()
            
            # Creación de la entrada en LogData
            LogData.objects.create(
                contraseña=contrasena.id,
                entidad='Contraseña',
                usuario=self.request.user,
                action='Create',
                password=contrasena.contraseña,
                detail=f'''Nombre: {contrasena.nombre_contra}, 
                           Seccion: {contrasena.seccion}, 
                           Usuario: {contrasena.usuario}, 
                           Link: {contrasena.link}, 
                           Info: {contrasena.info},
                           owner: {contrasena.owner}'''
            )

            # Gestión de permisos de acceso
            user_creator = self.request.user
            auto_permission_users = [user_creator]

            if not contrasena.is_personal:
                grant_permission_user_ids = settings.GRAN_PERMISSION_ID_USERS

                for user_id in grant_permission_user_ids:
                    try:
                        user = get_object_or_404(CustomUser, id=user_id)
                        if user not in auto_permission_users:
                            auto_permission_users.append(user)
                    except Http404:
                        continue

            for user in auto_permission_users:
                if user is not None:
                    try:
                        ContraPermission.objects.create(user_id=user, permission=True, contra_id=contrasena)
                    except Exception as e:
                        messages.error(self.request, f'Error al crear permiso de acceso: {e}')

            return super().form_valid(form)
        
        except IntegrityError:
            form.add_error('nombre_contra', 'El nombre de la contraseña ya existe. Por favor, elige otro.')
            return self.form_invalid(form)
        
class ContrasUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrasena
    form_class = ContrasenaUForm
    template_name = 'update-cont.html'
    success_url = reverse_lazy('listpass')
    login_url = 'login'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._objeto_previo = None

    def get(self, request, *args, **kwargs):
        # Verificar permisos antes de continuar
        users_permissions = ContraPermission.objects.filter(contra_id=self.kwargs['pk'], permission=True)
        print(f'users_permissions: {users_permissions}')
        lista_permision_user = [permision.user_id for permision in users_permissions]

        if request.user not in lista_permision_user:
            # Redirigir si no tiene permisos
            messages.error(request, 'No tienes permisos para ingresar a editar esta contraseña.')
            return redirect(reverse('listpass'))

        return super().get(request, *args, **kwargs)
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['title'] = 'Editar Contraseña'
        context['entity'] = 'Contraseña'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'edit new'
        context['user_id'] = user.id
        context['username'] = user.username

        # Obtener el objeto y desencriptar los datos
        objeto = self.get_object()
        context['decrypted_user'] = objeto.get_decrypted_user()
        context['decrypted_password'] = objeto.get_decrypted_password()
        
        return context
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        objeto = self.get_object()
        kwargs.update({
            'decrypted_user': objeto.get_decrypted_user(),
            'decrypted_password': objeto.get_decrypted_password(),
        })
        return kwargs

    def get_object(self, queryset=None):
        # Memoización del objeto
        if not self._objeto_previo:
            self._objeto_previo = super().get_object(queryset=queryset)
            LogData.objects.create(
                entidad='Contraseña', 
                action='edit old', 
                detail=f'''Nombre: {self._objeto_previo.nombre_contra}, 
                           Seccion: {self._objeto_previo.seccion}, 
                           Usuario: {self._objeto_previo.usuario}, 
                           Link: {self._objeto_previo.link}, 
                           Info: {self._objeto_previo.info},
                           owner: {self._objeto_previo.owner}''', 
                usuario=self.request.user, 
                contraseña=self._objeto_previo.id,
                password=self._objeto_previo.contraseña
            )
        return self._objeto_previo

    def form_valid(self, form):
        contrasena = form.save(commit=False)
        objeto_previo = self.get_object()
        context = self.get_context_data()
        
        old_password = objeto_previo.contraseña
        new_password = contrasena.encrypt_password()
        print(f'old contraseña: {old_password} | new contraseña: {new_password}')
        
        # Verifica si la contraseña ha cambiado
        if old_password != new_password:
            action = 'change pass'
        else:
            action = 'edit new'
        
        LogData.objects.create(
            contraseña=contrasena.pk,
            entidad=context['entity'],
            usuario=self.request.user,
            action=action,
            password=new_password,
            detail=f'''Nombre: {contrasena.nombre_contra},
                       Seccion: {contrasena.seccion},
                       Usuario: {contrasena.encrypt_user()},
                       Link: {contrasena.link},
                       Info: {contrasena.info},
                       owner: {contrasena.owner}'''
        )
        
        # Llama al método form_valid original para guardar la instancia
        response = super().form_valid(form)
        
        return response

class ContrasDeleteView(LoginRequiredMixin, DeleteView):
    model = Contrasena
    template_name = 'delete-cont.html'
    success_url = reverse_lazy('listpass') 
    login_url = 'login' 

    def form_valid(self, form, *args, **kwargs):
        
        response = super().form_valid(form)
        id_contraseña = self.kwargs['pk']
        context = ContrasDeleteView.get_context_data(self)
        contrasena = self.object
        contrasena.active = False
        contrasena.save()
        LogData.objects.create(contraseña = id_contraseña, 
                               entidad = context['entity'], 
                               usuario = self.request.user, 
                               action = context['action'],
                               password=contrasena.contraseña, 
                               detail = f'''Nombre: {contrasena.nombre_contra}, 
                                            Seccion: {contrasena.seccion},
                                            Usuario: {contrasena.usuario}, 
                                            Link:{contrasena.link}, 
                                            Info:{contrasena.info},
                                            owner: {contrasena.owner}''')
        return response 
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Contraseña'
        context['entity'] = 'Contraseñas'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'Inactive'
        return context
 

class SectionCreateView(LoginRequiredMixin, CreateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'create-sect.html'
    success_url = reverse_lazy('createpass')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Seccion'
        context['entity'] = 'Seccion'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'Create'
        return context

    def get_queryset(self):
        return SeccionContra.objects.get()
    
    def form_valid(self, form, *args, **kwargs):

        response = super().form_valid(form)
        #obtengo el objeto seccion a traves del form.save()
        seccion = form.save()

        LogData.objects.create(contraseña = seccion.id, 
                               entidad = 'Seccion', 
                               usuario = self.request.user, 
                               action = 'Create', 
                               detail = f'Nombre: {seccion.nombre_seccion}')
        return response


class SectionListView(LoginRequiredMixin, ListView):
    model = SeccionContra
    template_name = 'listsection.html'
    login_url = 'login'
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    
    
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            data= SeccionContra.objects.get(pk=request.POST['id']).toJSON()

        except Exception as e:
            data['error'] = str(e)
        
        messages.success(request,  f'La {self.model.__name__} ha sido creada exitosamente.')

        return JsonResponse(data)
    
    def get_queryset(self):
        return SeccionContra.objects.all()
    
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Secciones'
        return context

    
class SectionUpdateView(LoginRequiredMixin, UpdateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'update-sect.html'
    success_url = reverse_lazy('listsection')
    login_url = 'login'

    
    def get_context_data(self, **kwargs):
         context = super().get_context_data(**kwargs)
         context['title'] = 'Editar Seccion'
         context['entity'] = 'Seccion'
         context['list_url'] = reverse_lazy('listsection')
         context['action'] = 'edit new'
         return context
    
    
    def get_object(self, queryset=None):
        # Obtener el objeto del modelo que se va a actualizar
        objeto_previo = super().get_object(queryset=queryset)
        LogData.objects.create(entidad = 'Seccion', 
                               action= 'edit old' ,
                               detail= f'Nombre: {objeto_previo.nombre_seccion}', 
                               usuario=self.request.user, 
                               contraseña=objeto_previo.id)
        return objeto_previo
    

    def form_valid(self, form, *args, **kwargs):
        response = super().form_valid(form)
        context = SectionUpdateView.get_context_data(self)
        seccion = form.save()
        LogData.objects.create(contraseña = seccion.pk, 
                               entidad = context['entity'], 
                               usuario = self.request.user, 
                               action = context['action'], 
                               detail = f'Nombre: {seccion.nombre_seccion}')
        

        return response

class SectionDeleteView(LoginRequiredMixin, DeleteView):
    model = SeccionContra
    template_name = 'delete-sect.html'
    success_url = reverse_lazy('listsection')
    login_url = 'login'
    
   
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Seccion'
        context['entity'] = 'Seccion'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'Inactive'
        return context
    
    def form_valid(self, form, *args, **kwargs):
        
        response = super().form_valid(form)
        id_seccion = self.kwargs['pk']
        
        seccion = self.object
        seccion.active = False
        seccion.save()
        LogData.objects.create(contraseña = id_seccion, 
                               entidad = 'Seccion', 
                               usuario = self.request.user, 
                               action = 'inactive', 
                               detail = f'Nombre: {seccion.nombre_seccion}')
        
        return response 


class SectionActiveView(LoginRequiredMixin, DetailView):
    model = SeccionContra
    template_name = 'active-sect.html'
    success_url = reverse_lazy('listsection')
    login_url = 'login'

    def get_context_data(self, **kwargs):
          
          context = super().get_context_data(**kwargs)
          context['title'] = 'Activar Seccion'
          context['entity'] = 'Seccion'
          context['list_url'] = reverse_lazy('listsection')
          context['action'] = 'active'
            
          return context
    
    def post(self, request, pk,*args, **kwargs):
        
        seccion = self.get_object()
        #context = SectionActiveView.get_context_data(self)
        if seccion.active == True:
            seccion.active = False
        else:
            seccion.active = True
        seccion.save()
        LogData.objects.create(contraseña = seccion.id, 
                               entidad = 'Seccion', 
                               usuario = self.request.user, 
                               action = 'active', 
                               detail = f'Nombre: {seccion.nombre_seccion}')

        messages.success(request,  f'La {self.model.__name__} ha sido activada exitosamente.')

        return redirect('listsection')


class DescargarArchivo(LoginRequiredMixin, DetailView):
    model = Contrasena
    template_name = 'filedownload.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.file:
            raise Http404("No se encontró el archivo asociado a esta contraseña.")

        archivo = self.object.file
        response = HttpResponse(archivo, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename={}'.format(archivo.name)
        return response
    
@user_passes_test(is_administrator)
def denypermission(request, pk):
    permission = ContraPermission.objects.get(id=pk)
    permission.permission = False
    permission.save()
    notificacion_user = UserNotifications.objects.create(
                                                        id_contrasena = permission.contra_id,
                                                        id_user = permission.user_id,
                                                        type_notification = f'Se te denegó la contraseña {permission.contra_id.nombre_contra}',
                                                        comment = f'{request.user.username} denegó el acceso',
    )
    messages.success(request, f'Permiso denegado correctamente. {permission.user_id.first_name}, {permission.user_id.last_name} --> {permission.contra_id.nombre_contra}')
    return redirect(request.META.get('HTTP_REFERER', '/'))

@user_passes_test(is_administrator)
def encrypt_all():
    contraseñas = Contrasena.objects.all()
    encrypted_data = []

    for contraseña in contraseñas:
        if not contraseña.usuario.startswith("b'gAAAA"):
            print(f'contraseña id: {contraseña.id}')
            original_user = contraseña.usuario
            original_password = contraseña.contraseña
            contraseña.usuario = contraseña.encrypt_user()
            contraseña.contraseña = contraseña.encrypt_password()
            contraseña.save()
            encrypted_data.append((contraseña.id, original_user, original_password))
            print(f'contraseña encriptada : {contraseña.contraseña}')
    
    return encrypted_data


@user_passes_test(is_administrator)
def encrypt_log_data():
    log_entries = LogData.objects.filter(entidad='Contraseña')
    encrypted_log_data = []

    for entry in log_entries:
        try:
 
            # Encriptar la contraseña si no está encriptada
            if not entry.password.startswith("b'gAAAA"):
                original_password = entry.password
                entry.password = entry.encrypt_password()
                entry.save()
                encrypted_log_data.append((entry.id, original_password, entry.get_encrypted_user()))

            # Encriptar el usuario dentro del campo detail si no está encriptado
            encrypted_user = entry.get_encrypted_user()
            print(f'usuario encrypted: {encrypted_user}')
            if encrypted_user and not encrypted_user.startswith("b'gAAAA"):
                decrypted_user = entry.get_decrypted_user(encrypted_user)
                print(f'usuario decrypted: {decrypted_user}')
                encrypted_user = encrypt_data(decrypted_user).decode()
                print(f'usuario encrypted2: {encrypted_user}')

                # Reemplazar el usuario desencriptado con el encriptado
                entry.detail = entry.detail.replace(decrypted_user, encrypted_user)
                entry.save()

        except ObjectDoesNotExist:
            print(f'No se encontró la contraseña para el log con id {entry.id}')
        except Exception as e:
            print(f'Error processing log {entry.id}: {e}')
    
    return encrypted_log_data


@user_passes_test(is_administrator)
def encrypt_all_data(request):
    encrypted_contras = encrypt_all()
    encrypted_logs = encrypt_log_data()
    
    # Save the log for rollback purposes
    with open('encrypted_data.log', 'w') as f:
        for contras in encrypted_contras:
            f.write(f'Contrasena: {contras[0]}, Original User: {contras[1]}, Original Password: {contras[2]}\n')
        for log in encrypted_logs:
            f.write(f'LogData: {log[0]}, Original Password: {log[1]}, Original User: {log[2]}\n')
    
    # Asegurarse de que se retorna un objeto HttpResponse o un render apropiado
    return render(request, 'listpass.html', {'message': 'Todos los datos han sido encriptados.'})

# Function to rollback the encryption process
@user_passes_test(is_administrator)
def rollback_encryption(request):
    key = settings.CRYPTOGRAPHY_KEY
    cipher_suite = Fernet(key)
    
    with open('encrypted_data.log', 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith('Contrasena'):
                parts = line.strip().split(', ')
                contras_id = int(parts[0].split(': ')[1])
                original_user = parts[1].split(': ')[1]
                original_password = parts[2].split(': ')[1]
                
                try:
                    contras = Contrasena.objects.get(id=contras_id)
                    contras.usuario = original_user
                    contras.contraseña = original_password
                    contras.save()
                except ObjectDoesNotExist:
                    print(f'Contrasena con id {contras_id} no encontrada para rollback.')
            
            if line.startswith('LogData'):
                parts = line.strip().split(', ')
                log_id = int(parts[0].split(': ')[1])
                original_password = parts[1].split(': ')[1]
                original_user = parts[2].split(': ')[1]
                
                try:
                    log = LogData.objects.get(id=log_id)
                    log.password = original_password
                    
                    # Restaurar el usuario original en el campo detail
                    encrypted_user = log.get_encrypted_user()
                    if encrypted_user:
                        decrypted_user = decrypt_data(encrypted_user)
                        log.detail = log.detail.replace(encrypted_user, original_user)
                    
                    log.save()
                except ObjectDoesNotExist:
                    print(f'LogData con id {log_id} no encontrada para rollback.')
                except Exception as e:
                    print(f'Error processing rollback for log {log.id}: {e}')
    return render(request, 'listpass.html', {'messages': 'Se desencriptaron todas las contraseñas'})


@user_passes_test(is_administrator)
def remake_pass(request):

    contrasenas = Contrasena.objects.all()
    counter = 0
    except_counter = 0
    for contrasena in contrasenas:
        log_data_obj = LogData.objects.filter(contraseña=contrasena.id).order_by('-created').first()
        if log_data_obj is not None:
            log_data_obj_pass = log_data_obj.password
            with open ('log_pass.txt', 'a') as f:
                f.write(f'log_data_obj_pass:{contrasena.nombre_contra} | {decrypt_data(log_data_obj_pass)}\n' )
                try:
                    contrasena.contraseña = log_data_obj_pass
                    contrasena.save()
                    counter += 1
                except Exception as e:
                    f.write(f'log_data_obj_pass: {contrasena.nombre_contra} | {e}\n')
                    except_counter += 1
        else:
            except_counter +=1
            with open ('log_pass.txt', 'a') as f:
                f.write(f'log_data_obj_pass: {contrasena.nombre_contra} | no existe log\n')

    messages.success(request,f'Se copiaron las contraseñas. Exitosas: {counter} | erroneas: {except_counter}' )
        
    return render(request, 'listpass.html')