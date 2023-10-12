from django import forms
from login.models import CustomUser
from .models import ContraPermission
from passbase.models import Contrasena

class PermissionUserForm(forms.Form):
    def __init__(self, *args, **kwargs):
        
        super(PermissionUserForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
        

class PermisoForm(forms.Form):
    def __init__(self, usuario, *args, **kwargs):
        print(f'usuario (PermisoForms): {usuario} ')
        super().__init__(*args, **kwargs)
        contraseñas = Contrasena.objects.all()
        
        for contraseña in contraseñas:
            initial_value = False

            permission_exists = ContraPermission.objects.filter(user_id=usuario, contra_id=contraseña).exists()

            if permission_exists:
                permission_instance = ContraPermission.objects.get(user_id=usuario, contra_id=contraseña)
                initial_value = permission_instance.permission
                print(f'inicial_value: {initial_value}')
            
                
            choices = [('True', 'Sí'), ('False', 'No')]
            self.fields[f'permiso_{contraseña.nombre_contra}'] = forms.ChoiceField(
                label=contraseña.nombre_contra,
                choices=choices,
                initial=initial_value,
                widget=forms.RadioSelect(),
                required=False
            )
            print(self.fields[f'permiso_{contraseña.nombre_contra}'].initial)
            
        
# class PermissionForm(forms.Form):
#     def __init__(self, *args, **kwargs):
#         usuario_id = kwargs.pop('usuario', None)
#         contraseñas = kwargs.pop('contraseñas', None)  # Recupera la lista de contraseñas activas
#         super(PermissionForm, self).__init__(*args, **kwargs)

#         #usuario_id = request.session.get('usuario_seleccionado_id')
#         print(f'usuario_id: {usuario_id}')
        
            
#         if usuario_id is not None:
#             # Obtener las Contraseñas con 'active' igual a True
#             contraseñas_activas = Contrasena.objects.filter(active=True)
            
           
#             # Crear un diccionario para almacenar los valores iniciales de los campos
#             valores_iniciales = {}
            
#             for contraseña in contraseñas_activas:
#                 print(f'contraseña: {contraseña}')
#                 field_name = f'permiso_{contraseña.nombre_contra}'  # Nombre del campo
#                 self.fields[field_name] = forms.BooleanField(required=False)
                
#                 try:# Obtener el permiso correspondiente para esta contraseña
#                     permiso = ContraPermission.objects.filter(id=168).first()

#                     print(f'permiso: {permiso}')
#                     # Si se encuentra un permiso para esta contraseña, establecer el valor inicial
#                     valores_iniciales[field_name] = permiso.permission
#                 except ContraPermission.DoesNotExist:
#                     print('NO existe permiso, se pondrá en False')
#                     valores_iniciales[field_name] = False
   
#             # Asignar los valores iniciales al formulario
#             self.initial = valores_iniciales

   