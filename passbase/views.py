"""Vistas y endpoints que administran contraseñas, secciones y tareas de cifrado."""

from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from login.models import CustomUser
from accounts.models import TenantSettings
from django_tenants.utils import get_tenant
from notifications.models import UserNotifications
from passbase.crypto import credential_fingerprint, encrypt_data
from .forms import ContrasenaForm, ContrasenaUForm, SectionForm, CSVUploadForm
from .models import Contrasena, SeccionContra, LogData
from .access import accessible_credentials
from permission.models import ContraPermission
from django.contrib.auth.decorators import user_passes_test
import csv
import io
import logging

logger = logging.getLogger(__name__)

# Funcion para user_passes_test 
def is_administrator(user):
    """Valida que el staff o superusuario pueda acceder a vistas protegidas."""
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    """Detecta explícitamente al superadministrador global."""
    return user.is_superuser
#####################################

TEMPLATE_NAME = 'vault-list.html'
ENTITY_CONTRASENA = 'Contraseña'
ACCION_TYPE = 'edit new'
class ContrasListView(LoginRequiredMixin, ListView):
    """Lista solo metadatos de las credenciales autorizadas."""
    model = Contrasena
    template_name = TEMPLATE_NAME
    context_object_name = 'query_perm'
    login_url = 'login'

    def get_queryset(self):
        return accessible_credentials(self.request.user).select_related('seccion').order_by('seccion__nombre_seccion', 'nombre_contra')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Contraseñas'

        
        return context


class ContrasDetailView(LoginRequiredMixin, DetailView):
    model=Contrasena
    template_name = 'vault-detail.html'
    login_url = 'login'

    def get_queryset(self):
        return accessible_credentials(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        log_data = LogData.objects.filter(contraseña=self.kwargs['pk']).order_by('-created')[:10]
        users_permissions = ContraPermission.objects.filter(
            contra_id=self.kwargs['pk'], contra_id__is_personal=False, permission=True, perm_active=True,
        ).exclude(user_id=self.object.owner_id).select_related('user_id')
        logger.debug('user permissions: %s', users_permissions)

        context['log_data'] = log_data if log_data.exists() else None
        context['users_permissions'] = users_permissions

        return context


@login_required(login_url='login')
@require_POST
@never_cache
def reveal_credential(request, pk):
    """Entrega una credencial puntualmente, con el mismo permiso activo del detalle."""
    field = request.POST.get('field')
    if field not in ('username', 'password'):
        return JsonResponse({'error': 'Campo no válido.'}, status=400)
    credential = get_object_or_404(accessible_credentials(request.user), pk=pk)
    if request.user.is_superuser and not (credential.is_personal and credential.owner_id == request.user.pk):
        raise Http404
    value = credential.get_decrypted_user() if field == 'username' else credential.get_decrypted_password()
    response = JsonResponse({'value': value})
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response
    
        

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
        logger.debug('cleaned_Data keys: %s', list(cleaned_data.keys()))
        cleaned_data['owner'] = self.request.user
        
        try:
            with transaction.atomic():
                # Guarda el objeto usando form.save(commit=False) para no guardar inmediatamente
                contrasena = form.save(commit=False)
                contrasena.owner = self.request.user
                contraseña = cleaned_data.get('contraseña')
                usuario = cleaned_data.get('usuario')

                hash_combination = credential_fingerprint(usuario, contraseña)
                # Verifica si el hash ya existe en la base de datos
                objeto_repetido = Contrasena.objects.filter(hash=hash_combination).first()
                if objeto_repetido:
                    logger.info('hash already exists, existing object: %s', objeto_repetido)
                    messages.error(self.request, "La combinación de usuario y contraseña ya existe. Revisá los datos ingresados.")
                    return self.form_invalid(form)

                if contrasena:
                    contrasena.hash = hash_combination
                    contrasena.save()
            
                # Gestión de permisos de acceso
                user_creator = self.request.user
                auto_permission_users = [user_creator]

                if not contrasena.is_personal:
                
                    # Obtener TenantSettings asociado al cliente/tenant actual
                    client = getattr(self.request.user, 'client', None)
                    if client is None:
                        client = get_tenant(self.request)

                    tenant_settings = TenantSettings.for_client(client) if client else None
                    if tenant_settings:
                        grant_permission_user_ids = tenant_settings.set_admins.values_list('id', flat=True)
                        logger.debug('grant_permission_user_ids: %s', list(grant_permission_user_ids))
                    else:
                        grant_permission_user_ids = []

                    for user_id in grant_permission_user_ids:
                        try:
                            user = get_object_or_404(CustomUser.for_current_tenant(), id=user_id)
                            if user not in auto_permission_users:
                                auto_permission_users.append(user)
                        except Http404:
                            continue

                for user in auto_permission_users:
                    if user is not None:
                        ContraPermission.objects.create(
                            user_id=user, permission=True, perm_active=True, contra_id=contrasena,
                        )

                self.object = contrasena
                return redirect(self.success_url)
        
        except IntegrityError:
            form.add_error(None, 'No se pudo guardar la contraseña y sus permisos. Revisá los datos e intentá nuevamente.')
            return self.form_invalid(form)
        

def parse_bool(value):
    """Convierte varias variantes textuales en booleano."""
    if value is None:
        return False
    value_str = str(value).strip().lower().replace('“', '').replace('”', '').replace('"', '').replace("'", '')
    if value_str in ['true', 'verdadero', 'si', 'sí', '1']:
        return True
    elif value_str in ['false', 'falso', 'no', '0']:
        return False
    else:
        raise ValueError(f"'{value}': el valor debe ser Verdadero o Falso.")

@user_passes_test(is_administrator)        
def upload_csv(request):
    """ 
    Permite subir un csv con la información de las contraseñas. 
    Crea las contraseñas subidas y genera un CSV de errores para las filas que no se importaron.
    """
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES["file"]

            # Leer archivo con fallback de codificación
            raw_data = file.read()
            try:
                logger.debug('Intentando decodificar con UTF-8...')
                decoded_file = raw_data.decode("utf-8").splitlines()
            except UnicodeDecodeError:
                logger.warning('Error de decodificación con UTF-8, intentando con Latin-1...')
                decoded_file = raw_data.decode("latin1").splitlines()

            reader = csv.DictReader(decoded_file)

            password_entries = []
            error_rows = []

            for row in reader:
                if Contrasena.objects.filter(nombre_contra=row.get("nombre_contra")).exists():
                    row["error"] = f"La contraseña '{row.get('nombre_contra')}' ya existe"
                    error_rows.append(row)
                    continue

                owner = CustomUser.for_current_tenant().filter(username=row.get("owner")).first()
                if owner is None:
                    owner = CustomUser.for_current_tenant().filter(id=1).first()

                seccion_raw = row.get("seccion")
                seccion_nombre = seccion_raw.strip() if seccion_raw else None

                if not seccion_nombre:
                    row["error"] = "Falta el nombre de la sección"
                    error_rows.append(row)
                    continue

                seccion, _ = SeccionContra.objects.get_or_create(
                    nombre_seccion=seccion_nombre,
                    defaults={"nombre_seccion": seccion_nombre}
                    )

                contrasena_encriptada = encrypt_data(row.get('contrasena'))
                usuario_encriptado = encrypt_data(row.get('usuario'))

                try:
                    is_personal_value = parse_bool(row.get("is_personal"))
                except ValueError as e:
                    row["error"] = str(e)
                    error_rows.append(row)
                    continue
                try:
                    password_entries.append(Contrasena(
                        nombre_contra = row.get("nombre_contra"),
                        seccion = seccion,
                        link = row.get("link"),
                        usuario = usuario_encriptado,
                        contraseña = contrasena_encriptada,
                        actualizacion = row.get("actualizacion"),
                        info = row.get("info"),
                        is_personal = is_personal_value,
                        owner = owner,
                        hash = credential_fingerprint(row.get('usuario'), row.get('contrasena')),
                    ))
                except KeyError as e:
                    row["error"] = f"Error en la columna: {e}"
                    error_rows.append(row)
                    continue

            if password_entries:
                try:
                    Contrasena.bulk_create_with_logs(password_entries)
                    messages.success(request, "Contraseñas cargadas correctamente.")
                except Exception as e:
                    messages.error(request, f"ERROR de importación: {e}")
                    return redirect("config")

            if error_rows:
                output = io.StringIO()
                fieldnames = reader.fieldnames + ["error"] if reader.fieldnames else ["error"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for error_row in error_rows:
                    writer.writerow(error_row)
                response = HttpResponse(output.getvalue(), content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="errores_importacion.csv"'
                messages.success(request, f"No se pudieron importar {len(error_rows)} contraseñas. Revise el csv de errores.")
                return response  # <--- Debe devolver el archivo, no redirigir

    else:
        form = CSVUploadForm()

    return render(request, "upload_csv.html", {"form": form})



@method_decorator(never_cache, name='dispatch')
class ContrasUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrasena
    form_class = ContrasenaUForm
    template_name = 'update-cont.html'
    success_url = reverse_lazy('listpass')
    login_url = 'login'

    def get_queryset(self):
        return accessible_credentials(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['title'] = 'Editar Contraseña'
        context['entity'] = ENTITY_CONTRASENA
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = ACCION_TYPE
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
            'actor': self.request.user,
            'decrypted_user': objeto.get_decrypted_user(),
            'decrypted_password': objeto.get_decrypted_password(),
        })
        return kwargs

    def form_valid(self, form):
        old = Contrasena.objects.get(pk=self.object.pk)
        changed_password = form.cleaned_data['contraseña'] != old.get_decrypted_password()
        if changed_password or form.cleaned_data['usuario'] != old.get_decrypted_user():
            form.instance.hash = credential_fingerprint(form.cleaned_data['usuario'], form.cleaned_data['contraseña'])
        response = super().form_valid(form)
        LogData.objects.create(
            contraseña=self.object.pk,
            entidad=ENTITY_CONTRASENA,
            usuario=self.request.user,
            action='change pass' if changed_password else ACCION_TYPE,
            password='[REDACTED]',
            detail=f"Nombre: {self.object.nombre_contra}, Seccion: {self.object.seccion_id}, owner: {self.object.owner_id}",
        )
        return response

class ContrasDeleteView(LoginRequiredMixin, DeleteView):
    model = Contrasena
    template_name = 'delete-cont.html'
    success_url = reverse_lazy('listpass') 
    login_url = 'login' 

    def get_queryset(self):
        queryset = Contrasena.objects.filter(active=True)
        if self.request.user.is_superuser:
            return queryset.filter(is_personal=False) | queryset.filter(owner=self.request.user)
        return queryset.filter(owner=self.request.user)

    def form_valid(self, form, *args, **kwargs):
        contrasena = self.object
        Contrasena.objects.filter(pk=contrasena.pk).update(active=False)
        LogData.objects.create(
            contraseña=contrasena.pk,
            entidad='Contrasena',
            usuario=self.request.user,
            action='Inactive',
            password='[REDACTED]',
            detail=f'Nombre: {contrasena.nombre_contra}',
        )
        return redirect(self.success_url)
    
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
    template_name = 'vault-sections.html'
    login_url = 'login'
    
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
         context['action'] = ACCION_TYPE
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
        context['title'] = 'Desactivar sección'
        context['entity'] = 'Seccion'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'Desactivar'
        return context
    
    def form_valid(self, form, *args, **kwargs):
        seccion = self.object
        SeccionContra.objects.filter(pk=seccion.pk).update(active=False)
        LogData.objects.create(
            contraseña=seccion.pk,
            entidad='Seccion',
            usuario=self.request.user,
            action='inactive',
            detail=f'Nombre: {seccion.nombre_seccion}',
        )
        
        return redirect(self.success_url)


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

    def get_queryset(self):
        return accessible_credentials(self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.file:
            raise Http404("No se encontró el archivo asociado a esta contraseña.")

        archivo = self.object.file
        response = HttpResponse(archivo, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename={}'.format(archivo.name)
        return response
    
@user_passes_test(is_administrator)
@require_POST
def denypermission(request, pk):
    permission = get_object_or_404(ContraPermission.objects.select_related('contra_id'), id=pk, contra_id__is_personal=False)
    if permission.contra_id.owner_id == permission.user_id_id:
        messages.warning(request, 'El propietario mantiene acceso a su contraseña.')
        return redirect('detailpass', pk=permission.contra_id_id)
    permission.permission = False
    permission.save()
    notificacion_user = UserNotifications.objects.create(
                                                        id_contrasena = permission.contra_id,
                                                        id_user = permission.user_id,
                                                        type_notification = f'Se te denegó la contraseña {permission.contra_id.nombre_contra}',
                                                        comment = f'{request.user.username} denegó el acceso',
    )
    logger.info('notificacion creada: %s', notificacion_user)
    messages.success(request, f'Permiso denegado correctamente. {permission.user_id.first_name}, {permission.user_id.last_name} --> {permission.contra_id.nombre_contra}')
    return redirect('detailpass', pk=permission.contra_id_id)
