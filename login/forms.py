from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser, GlobalSettings
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3




class CustomLoginForm(AuthenticationForm):
    captcha = ReCaptchaField(
    widget=ReCaptchaV3(
        attrs={
            'required_score':0.8, #aumenta el score de puntuacion para la deteccion de bots
            
        }
    )
)
    
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    password1 = forms.CharField(label = 'Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label = 'Confirmar Contraseña', widget=forms.PasswordInput)
    captcha = ReCaptchaField(
    widget=ReCaptchaV3(
        attrs={
            'required_score':0.8, #aumenta el score de puntuacion para la deteccion de bots
            }
        )
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        help_texts = {k:"" for k in fields}
    
    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password1'] != cd['password2']:
            raise forms.ValidationError('Las contraseñas no coinciden')
        return cd['password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'


class ProfileForm(forms.ModelForm):
    menu_color = forms.CharField(
        max_length=7,  # El valor hexadecimal del color es de 7 caracteres (#XXXXXX)
        widget=forms.TextInput(attrs={'type': 'color'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'avatar', 'position', 'menu_color', 'is_2fa_enabled']
    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_2fa_enabled':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif name == 'avatar':
                field.widget.attrs.update({'class': 'form-control form-control-sm', 'id': 'id_avatar'})
            elif name == 'menu_color':
                field.widget.attrs.update({'class': 'form-control form-control-color', 'style': 'height:44px; width:120px;'})
            else:
                field.widget.attrs.update({'class': 'form-control', 'autocomplete': 'off'})



class UserForm(forms.ModelForm):
    admission_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control' }),required=False)
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control' }),required=False)
    is_superuser = forms.RadioSelect()
    is_staff = forms.RadioSelect()
    is_active = forms.RadioSelect()
    documento = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    position = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    tel_number = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'documento', 'birth_date','address', 'tel_number','is_superuser', 'is_staff',  'is_active' ,'position', 'admission_date']
        

class UserDepartureForm(forms.ModelForm):
     departure_date = forms.DateField(label= 'Fecha de baja',widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
     departure_motive = forms.CharField(label= 'Motivo de baja',widget=forms.Textarea(attrs={'class': 'form-control'}))
     class Meta:
        model = CustomUser
        fields = ['departure_date', 'departure_motive', 'is_active']

        

   


class AdminLoginForm(AuthenticationForm):
    captcha = ReCaptchaField(
    widget=ReCaptchaV3(
        attrs={
            'required_score':0.8, #aumenta el score de puntuacion para la deteccion de bots
            
        }
    )
)    

class GlobalSettingsForm(forms.ModelForm):
    menu_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
    )
    
    class Meta:
        model = GlobalSettings
        fields = ['company_name','multifactor_status', 'is_admin_dash_active', 'menu_color', 'set_admins']
        widgets = {
            'company_name': forms.TextInput(attrs={'class':'form-control'}),
            'multifactor_status': forms.Select(attrs={'class': 'form-select'}),
            'is_admin_dash_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'menu_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
            'set_admins': forms.SelectMultiple(attrs={'class': 'form-control'})
        }