from django import forms
from login.models import CustomUser

class PermissionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        contraseñas = kwargs.pop('contraseñas', None)
        super(PermissionForm, self).__init__(*args, **kwargs)
        
        self.fields['usuario'] = forms.ModelChoiceField(queryset=CustomUser.objects.all())
        
        for contraseña in contraseñas:
            self.fields[contraseña.nombre_contra] = forms.BooleanField(required=False)