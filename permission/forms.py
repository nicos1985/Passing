from django import forms
from login.models import CustomUser
from .models import ContraPermission

class PermissionUserForm(forms.Form):
    def __init__(self, *args, **kwargs):
        contraseñas = kwargs.pop('contraseñas', None)
        super(PermissionUserForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all())
        

class PremissionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        contraseñas = kwargs.pop('contraseñas', None)
        super(PremissionForm, self).__init__(*args, **kwargs)
        
        usuario_id = self.request.session.get('usuario_seleccionado_id')
        print(f'usuario_id: {usuario_id}')
        permisos_usuario = ContraPermission.objects.filter(user_id=usuario_id)
        print(f'permisos_usuario: {permisos_usuario}')

        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all())
        for contraseña in permisos_usuario:
            self.fields[contraseña.nombre_contra] = forms.BooleanField(required=False, initial=contraseña.permission)

        