from django import forms
from login.models import CustomUser
from .models import ContraPermission
from passbase.models import Contrasena

class PermissionUserForm(forms.Form):
    def __init__(self, *args, **kwargs):
        
        super(PermissionUserForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all())
        
# class PermissionForm(forms.Form):
#     def __init__(self, *args, **kwargs):
#         contraseñas = kwargs.pop('contraseñas', None)
#         super(PermissionForm, self).__init__(*args, **kwargs)
        
#         usuario_id = self.request.session.get('usuario_seleccionado_id')
#         print(f'usuario_id: {usuario_id}')
#         permisos_usuario = ContraPermission.objects.filter(user_id=usuario_id)
#         print(f'permisos_usuario: {permisos_usuario}')

#         self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all())
#         for contraseña in permisos_usuario:
#             self.fields[contraseña.nombre_contra] = forms.BooleanField(required=False, initial=contraseña.permission)

        
class PermissionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super(PermissionForm, self).__init__(*args, **kwargs)

        usuario_id = request.session.get('usuario_seleccionado_id')
        if usuario_id is not None:
            # Obtener las Contraseñas con 'active' igual a True
            contraseñas_activas = Contrasena.objects.filter(active=True)
            
            # Obtener los permisos del usuario seleccionado
            permisos_usuario = ContraPermission.objects.filter(user_id=usuario_id)
            
            # Crear un diccionario para almacenar los valores iniciales de los campos
            valores_iniciales = {}
            
            for contraseña in contraseñas_activas:
                field_name = f"permiso_{contraseña.nombre_contra}"  # Nombre del campo
                self.fields[field_name] = forms.BooleanField(required=False)
                
                # Obtener el permiso correspondiente para esta contraseña
                permiso = permisos_usuario.filter(contraseña=contraseña).first()
                
                # Si se encuentra un permiso para esta contraseña, establecer el valor inicial
                if permiso:
                    valores_iniciales[field_name] = permiso.permission
            
            # Asignar los valores iniciales al formulario
            self.initial = valores_iniciales

   