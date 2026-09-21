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
        permissions = {p.contra_id_id: p for p in ContraPermission.objects.filter(user_id=usuario)}
        for credential in Contrasena.objects.filter(is_personal=False, active=True).select_related('seccion', 'owner').order_by('seccion_id', 'pk'):
            permission = permissions.get(credential.pk)
            self.fields[f'permiso_{credential.pk}'] = forms.BooleanField(
                label=credential.nombre_contra, required=False,
                initial=bool(permission and permission.permission == 'True' and permission.perm_active),
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input',
                    'seccion': credential.seccion, 'info': credential.info, 'usuario': credential.owner or ''}))


class CustomModelChoiceIterator(ModelChoiceIterator):
    def choice(self, obj):
        return (self.field.prepare_value(obj), self.field.label_from_instance(obj))

class CustomModelChoiceField(ModelMultipleChoiceField):
    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CustomModelChoiceIterator(self)

    def _set_choices(self, value):
        self._choices = value

    choices = property(_get_choices, _set_choices)


class PermissionRolesForm(forms.ModelForm):
    rol_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    contrasenas = CustomModelChoiceField(
        queryset=Contrasena.objects.filter(is_personal=False, active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='Contraseñas',
    )
    comment = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = PermissionRoles
        fields = ['rol_name', 'contrasenas', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['contrasenas'].initial = self.instance.contrasenas.all()
        


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
        self.fields['rol'].queryset = PermissionRoles.objects.filter(is_active=True)