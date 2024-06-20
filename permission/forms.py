from collections import OrderedDict
from django import forms
from login.models import CustomUser
from .models import ContraPermission, PermissionRoles, UserRoles
from passbase.models import Contrasena, LogData
from django.forms.models import ModelChoiceField, ModelChoiceIterator, ModelMultipleChoiceField

class PermissionUserForm(forms.Form):
    def __init__(self, *args, **kwargs):
        
        super(PermissionUserForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.filter(is_active=True), 
                                                        widget=forms.Select(attrs={'class': 'form-select'}))
        

class PermisoForm(forms.Form):
    def __init__(self, usuario, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        contraseñas = Contrasena.objects.filter(is_personal=False)
        
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

class CustomModelChoiceIterator(ModelChoiceIterator):
    def choice(self, obj):
        return (self.field.prepare_value(obj),
                self.field.label_from_instance(obj), obj)
    

class CustomModelChoiceField(ModelMultipleChoiceField):
    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CustomModelChoiceIterator(self)
    choices = property(_get_choices,  
                       forms.MultipleChoiceField._set_choices)
class PermissionRolesForm(forms.ModelForm):
    rol_name = forms.CharField()
    contrasenas = CustomModelChoiceField(
        queryset=Contrasena.objects.filter(is_personal=False),
        widget=forms.CheckboxSelectMultiple,
        label='Contraseñas',
    )

    class Meta:
        model = PermissionRoles
        fields = ['rol_name', 'contrasenas']


class UserRolForm(forms.ModelForm):
    class Meta:
        model = UserRoles
        fields = ['user', 'rol']
        labels = {
            'user': 'Usuario',
            'rol': 'Rol'
        }
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserRolForm, self).__init__(*args, **kwargs)
        self.fields['user'].queryset = CustomUser.objects.filter(is_active=True)
        self.fields['rol'].queryset = PermissionRoles.objects.all()