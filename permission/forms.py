from collections import OrderedDict
from django import forms
from login.models import CustomUser
from .models import ContraPermission
from passbase.models import Contrasena, LogData

class PermissionUserForm(forms.Form):
    def __init__(self, *args, **kwargs):
        
        super(PermissionUserForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
        

class PermisoForm(forms.Form):
    def __init__(self, usuario, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        contraseñas = Contrasena.objects.all()
        
        for contraseña in contraseñas:
            initial_value = False
            log_contra_user_id = LogData.objects.filter(entidad='Contraseña',contraseña=int(contraseña.id), action='Create').exists() #reviso si existe el log create de la contraseña

            permission_exists = ContraPermission.objects.filter(user_id=usuario, contra_id=contraseña).exists()

            if log_contra_user_id:

                log_contra_user_id = LogData.objects.get(entidad='Contraseña',contraseña=int(contraseña.id), action='Create').usuario #traigo usuario creador de contraseña

                if permission_exists:
                    permission_instance = ContraPermission.objects.get(user_id=usuario, contra_id=contraseña)
                    initial_value = permission_instance.permission
                    
                    self.fields[f'permiso_{contraseña.nombre_contra}'] = forms.BooleanField(
                        label=contraseña.nombre_contra,
                        initial=initial_value,
                        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'seccion': contraseña.seccion, 'info': contraseña.info, 'usuario': log_contra_user_id} ),
                        required=False
                        )
                
                else:
                    self.fields[f'permiso_{contraseña.nombre_contra}'] = forms.BooleanField(
                    label=contraseña.nombre_contra,
                    initial=False,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'seccion': contraseña.seccion, 'info': contraseña.info, 'usuario': log_contra_user_id} ),
                    required=False
                    )
            else:
                log_contra_user_id = None    

   # Obtén los campos originales
        fields = list(self.fields.items())
        print(f'fields: {fields}')
      

        # Ordena los campos según el atributo 'seccion' del widget
        fields.sort(key=lambda x: str(x[1].widget.attrs.get('seccion', '')))

        # Asigna los campos ordenados de nuevo al formulario
        self.fields = OrderedDict(fields)
        
            
            
        
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

   