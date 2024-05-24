from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

from notifications.models import UserNotifications
from .forms import ContrasenaForm, ContrasenaUForm, SectionForm
from .models import Contrasena, SeccionContra, LogData
from permission.models import ContraPermission
from django.utils import timezone


class ContrasListView(LoginRequiredMixin, ListView):
    model = Contrasena
    template_name = 'listpass.html'
    context_object_name = 'query_perm'
    login_url = 'login'

    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
 
    def post(self, request, *args, **kwargs):
         data = {}
         try:
             data= Contrasena.objects.get(pk=request.POST['id']).toJSON()
 
         except Exception as e:
             data['error'] = str(e)
    
         return JsonResponse(data)
    
    def get_queryset(self):

        log_data ={}
        
        fecha_hoy = timezone.now()

    #try: 
        # busco los objetos de permiso con el user logueado y extraigo los id de contraseña. 
        obj_permiso = ContraPermission.objects.filter(user_id = self.request.user, 
                                                    perm_active = True, 
                                                    permission = True).values_list('contra_id', flat=True)
        #convierto en lista
        permisos = list(obj_permiso)
        #retorno solo los objetos en los que el id se encuentran dentro de la lista
        print(f'permisos: {permisos}')

        query_perm = Contrasena.objects.filter(active=True, id__in = permisos).order_by('seccion')

        def ratio_calculation(created_value):
            dias_actualizacion = Contrasena.objects.get(id=contrasena.id).actualizacion
            dias_transcurridos = fecha_hoy - created_value
            dias_faltantes = dias_actualizacion - int(dias_transcurridos.days)
            try:
                ratio = dias_faltantes / dias_actualizacion
            except:
                ratio = 0

            if ratio <= 0:
                log_data[contrasena.id] = 'rojo'
               
            elif 0.01 < ratio <= 0.09:
                log_data[contrasena.id] = 'amarillo'
               
                
            elif ratio > 0.09:
                log_data[contrasena.id] = 'verde'
               
        
        for contrasena in query_perm:
            # Buscar registros con action='change pass'
            
            log_data_change_pass = LogData.objects.filter(contraseña=contrasena.id, action='change pass').order_by('-created')[:1]
            

            # Si no se encontraron registros con action='change pass', buscar con action='created'
            if log_data_change_pass.exists():
                log_data_objeto = log_data_change_pass.first()
                created_value = log_data_objeto.created
                ratio_calculation(created_value)


            else:
                # Si no hay registros 'change pass', intenta con 'created'
                log_data_created = LogData.objects.filter(
                    contraseña=contrasena.id, action='Create'
                ).order_by('-created')[:1]

                if log_data_created.exists():
                    log_data_objeto = log_data_created.first()
                    changed_value = log_data_objeto.created
                    ratio_calculation(changed_value)
                
                else:
                    # Manejar el caso en el que no hay registros 'change pass' ni 'created'
                    print('No hay registros "change pass" ni "created"')


        for contrasena in query_perm:
            # Agrega un nuevo atributo 'flag' a cada objeto en el queryset
            contrasena.flag = log_data.get(contrasena.id, 'sin_color')

        print(query_perm)
        return query_perm
    
    #except Exception as e:
        print(f'error: {e}')
        return redirect(reverse_lazy('login'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Contraseñas'

        
        return context


class ContrasDetailView(LoginRequiredMixin, DetailView):
    model=Contrasena
    template_name = 'detail-cont.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
    
        log_data =  LogData.objects.filter(contraseña=self.kwargs['pk']).order_by('-created')[:10]
        dias_actual_contrasena = Contrasena.objects.get(id=self.kwargs['pk']).actualizacion
        users_permissions = ContraPermission.objects.filter(contra_id=self.kwargs['pk'],permission=True)
        
        try:
            fecha_ult_up_pass= LogData.objects.filter(contraseña=self.kwargs['pk'], action = 'change pass').order_by('-created').first().created
            fecha_hoy = timezone.now()
            diferencia = fecha_hoy - fecha_ult_up_pass
            cant_dias = diferencia.days 
            
        except:
            fecha_ult_up_pass= LogData.objects.filter(contraseña=self.kwargs['pk'], action = 'Create').order_by('-created').first().created
            fecha_hoy = timezone.now()
            diferencia = fecha_hoy - fecha_ult_up_pass
            cant_dias = diferencia.days 
                            
        if log_data.exists():
            context['log_data'] = log_data
            context['last_update'] = cant_dias
            context['actualizacion'] = dias_actual_contrasena
            context['users_permisions'] = users_permissions

        else:
            context['log_data'] = None
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
        context['sections'] =  SeccionContra.objects.filter(active=True)
        return context
    

    
    def form_valid(self,form, *args, **kwargs):
        
        response = super().form_valid(form)
        #obtengo el objeto contraseña a traves del form.save()
        contrasena = form.save()
        
        LogData.objects.create(contraseña = contrasena.id , 
                               entidad = 'Contraseña', 
                               usuario = self.request.user , 
                               action = 'Create',
                               password=contrasena.contraseña,
                               detail = f'''Nombre: {contrasena.nombre_contra}, 
                                                    Seccion: {contrasena.seccion}, 
                                                    Usuario: {contrasena.usuario}, 
                                                    Link:{contrasena.link}, 
                                                    Info:{contrasena.info}''')
        ContraPermission.objects.create(user_id=self.request.user,
                                        permission=True,
                                        contra_id=contrasena
                                        )
        return response
        
class ContrasUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrasena
    form_class = ContrasenaUForm
    template_name = 'update-cont.html'
    success_url = reverse_lazy('listpass')
    login_url = 'login'
    
    
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
         
         return context
    

    def get_object(self, queryset=None):
        # Obtener el objeto del modelo que se va 
        objeto_previo = super().get_object(queryset=queryset)
        LogData.objects.create(entidad = 'Contraseña', 
                               action= 'edit old', 
                               detail= f'''Nombre: {objeto_previo.nombre_contra}, 
                                           Seccion: {objeto_previo.seccion}, 
                                           Usuario: {objeto_previo.usuario}, 
                                           Link:{objeto_previo.link}, 
                                           Info:{objeto_previo.info}''', 
                               usuario=self.request.user, 
                               contraseña=objeto_previo.id,
                               password=objeto_previo.contraseña)
        
        return objeto_previo

    def form_valid(self, form, *args, **kwargs):
        contrasena = form.save(commit=False)
        objeto_previo = Contrasena.objects.get(id=self.kwargs['pk'])
        context = self.get_context_data()
        print(f'old_contra: {objeto_previo.contraseña} == new_contra: {contrasena.contraseña}')
    # Verifica si la contraseña ha cambiado
        if objeto_previo.contraseña != contrasena.contraseña:
            action = 'change pass'
        else:
            action = 'edit new'
        
        LogData.objects.create(
            contraseña=contrasena.pk,
            entidad=context['entity'],
            usuario=self.request.user,
            action=action,
            password=contrasena.contraseña,
            detail=f'''Nombre: {contrasena.nombre_contra},
                        Seccion: {contrasena.seccion},
                        Usuario: {contrasena.usuario},
                        Link: {contrasena.link},
                        Info: {contrasena.info}'''
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
                                            Info:{contrasena.info}''')
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


class DescargarArchivo(DetailView):
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


