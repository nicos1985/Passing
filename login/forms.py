from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import CustomUser
from django.contrib.auth.views import LoginView, LogoutView

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    password1 = forms.CharField(label = 'Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label = 'Confirmar Contraseña', widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']
        help_texts = {k:"" for k in fields}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'


class ProfileForm(forms.ModelForm):

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'avatar', 'position']

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)