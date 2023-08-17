from django.shortcuts import render
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, FormView
from .models import ContraPermission
from passbase.models import Contrasena
from .forms import PermissionForm
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
    
    template_name = 'create-perm.html'
    form_class = PermissionForm
    

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contraseñas'] = Contrasena.objects.filter(active = True)
        return kwargs

    def form_valid(self, form):
        contraseñas = self.get_form_kwargs().get('contraseñas', None)
        if contraseñas is not None:
            usuario_id = form.cleaned_data['usuario']
            permisos = ContraPermission.objects.filter(user_id=usuario_id)
            
            for contraseña in contraseñas:
                valor = form.cleaned_data[contraseña.nombre_contra]
                print(f'valor: {valor}')
                
                for permiso in permisos:
                    
                    print(f'permiso: {permiso.contra_id} || {contraseña}')
                    if permiso.contra_id == contraseña:
                        print(f'update: {contraseña} = {valor}')
                        ContraPermission.objects.get(id).update(permission=valor)
                        
                        break

            ContraPermission.objects.create(contra_id=contraseña, user_id=usuario_id, permission=valor)
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('listpass')