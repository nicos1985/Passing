from typing import Any

from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ContrasenaForm, ContrasenaUForm, SectionForm
from .models import Contrasena, SeccionContra, LogData
from permission.models import ContraPermission
from django.utils import timezone
from datetime import timedelta



class ContrasListView(ListView):
    model = Contrasena
    template_name = 'listpass.html'

    
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
        try: 
            # busco los objetos de permiso con el user logueado y extraigo los id de contraseña. 
            obj_permiso = ContraPermission.objects.filter(user_id = self.request.user, perm_active = True, permission = True).values_list('contra_id', flat=True)
            #convierto en lista
            permisos = list(obj_permiso)
            #retorno solo los objetos en los que el id se encuentran dentro de la lista
            print(f'permisos: {permisos}')
            return Contrasena.objects.filter(active=True, id__in = permisos)
        except Exception as e:
            return redirect(reverse_lazy('login'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Contraseñas'
        return context


class ContrasDetailView(DetailView):
    model=Contrasena
    template_name = 'detail-cont.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
    #hacer que esto esté por cada fecha del logdata
        log_data =  LogData.objects.filter(contraseña=self.kwargs['pk'])[:10]
        fecha_ult_up_pass= LogData.objects.filter(contraseña=self.kwargs['pk'], action = 'change pass').order_by('-created').first().created
        fecha_hoy = timezone.now()
        diferencia = fecha_hoy - fecha_ult_up_pass
        cant_dias = diferencia.days 
        print(f'cantidad de dias: {cant_dias}')
                            
        if log_data.exists():
            context['log_data'] = log_data
            context['last_update'] = cant_dias

        else:
            context['log_data'] = None           
        return context

class ContrasCreateView(CreateView):
    model = Contrasena, SeccionContra
    form_class = ContrasenaForm
    template_name = 'create-cont.html'
    success_url = reverse_lazy('listpass')

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
                               detail = f'''Nombre: {contrasena.nombre_contra}, 
                                                    Seccion: {contrasena.seccion}, 
                                                    Usuario: {contrasena.usuario}, 
                                                    Link:{contrasena.link}, 
                                                    Info:{contrasena.info}''')
        return response
    
    
class ContrasUpdateView(UpdateView):
    model = Contrasena
    form_class = ContrasenaUForm
    template_name = 'update-cont.html'
    success_url = reverse_lazy('listpass')
    
    
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
                               contraseña=objeto_previo.id)
        
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
            detail=f'''Nombre: {contrasena.nombre_contra},
                        Seccion: {contrasena.seccion},
                        Usuario: {contrasena.usuario},
                        Link: {contrasena.link},
                        Info: {contrasena.info}'''
        )
        
        # Llama al método form_valid original para guardar la instancia
        response = super().form_valid(form)
        
        return response
       

class ContrasDeleteView(DeleteView):
    model = Contrasena
    template_name = 'delete-cont.html'
    success_url = reverse_lazy('listpass')  

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
 

class SectionCreateView(CreateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'create-sect.html'
    success_url = reverse_lazy('createpass')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Seccion'
        context['entity'] = 'Seccion'
        context['list_url'] = reverse_lazy('listpass')
        context['action'] = 'add'
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
                               action = 'add', 
                               detail = f'Nombre: {seccion.nombre_seccion}')
        return response


class SectionListView(ListView):
    model = SeccionContra
    template_name = 'listsection.html'
    
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

    
class SectionUpdateView(UpdateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'update-sect.html'
    success_url = reverse_lazy('listsection')

    
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

class SectionDeleteView(DeleteView):
    model = SeccionContra
    template_name = 'delete-sect.html'
    success_url = reverse_lazy('listsection')
    
   
    
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


class SectionActiveView(DetailView):
    model = SeccionContra
    template_name = 'active-sect.html'
    success_url = reverse_lazy('listsection')

    def get_context_data(self, **kwargs):
          
          context = super().get_context_data(**kwargs)
          context['title'] = 'Activar Seccion'
          context['entity'] = 'Seccion'
          context['list_url'] = reverse_lazy('listsection')
          context['action'] = 'activar'
            
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
