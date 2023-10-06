from django.shortcuts import redirect, render
from django import forms
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, FormView
from .models import ContraPermission
from passbase.models import Contrasena
from .forms import PermissionUserForm, PermissionForm
# Create your views here.

class PermissionListView(ListView):
    model = ContraPermission
    template_name = 'listpermission.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Permisos'
        return context
    
    def get_queryset(self):
        
        return ContraPermission.objects.all()
    

class PermissionFormView(FormView):
    
    template_name = 'create-perm-p2.html'
    form_class = PermissionForm
    
    def get_initial(self):
        # Obten el objeto request de la redirección
        request = self.request
        return {'request': request}  # Esto inicializa el campo 'request' en Form2

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request['usuario']
        kwargs['contraseñas'] = Contrasena.objects.filter(active=True)
        return kwargs
    
  
    # def get_form(self, form_class=None):
    #     # Recuperar el usuario seleccionado de la sesión
    #     usuario_id = self.request.session.get('usuario_seleccionado_id')
        
    #     # Recuperar los valores de la base de datos correspondientes al usuario
    #     permisos_usuario = ContraPermission.objects.filter(user_id=usuario_id)
        
    #     # Pasar los valores recuperados al formulario
    #     form = super().get_form(form_class)
    #     for contraseña in contraseñas:
    #         self.fields[contraseña.nombre_contra] = forms.BooleanField(required=False, initial=contraseña.permission)
        
    #     return form
    

    def form_valid(self, form):

        
        # contraseñas = self.get_form_kwargs().get('contraseñas', None) #recupera las contraseñas Activas de kwargs
        # if contraseñas is not None:
        #     usuario_id = form.cleaned_data['usuario'] #obtengo el usuario del formulario

        #     for contraseña in contraseñas: #recorro cada contraseña y filtro los permisos dados. 
        #         valor = form.cleaned_data[contraseña.nombre_contra]
        #         print(f'valor: {valor}')
        #         permiso = ContraPermission.objects.filter(user_id=usuario_id, contra_id = contraseña)
        #         print(f'objetos permisos : {permiso}')

        #         if permiso.exists():
                    
        #             print(f'update: {contraseña} = {valor}')
        #             permiso.update(permission=valor) #si existe el permiso, le doy el valor del formulario (actualiza)
                    
        #         else:    # si no existe el permiso de esa contraseña, lo creo con los valores dados en el form. 
        #             print('crea objeto sin query')
        #             ContraPermission.objects.create(contra_id=contraseña, user_id=usuario_id, permission=valor)
        return redirect('listpass')
    
    
    
class PermissionUserFormView(FormView):

    template_name = 'create-perm-p1.html'
    form_class = PermissionUserForm

    def form_valid(self, request, form):
        # Almacenar el usuario seleccionado en la sesión
        usuario = form.cleaned_data['usuario']
        print(f"usuario de sesion: {self.request.session['usuario_seleccionado_id']}")

        # Resto de la lógica del formulario PermissionUserForm
        return redirect('permissionform2', request ={'usuario' : usuario })  # Usa el nombre de la URL
        
    
