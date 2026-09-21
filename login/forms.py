from django import forms
from django.conf import settings
import logging

from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3




class LoggedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        users = list(super().get_users(email))
        logger = logging.getLogger('passing.mail')
        if users:
            logger.info('Password reset: eligible_accounts=%s', len(users))
        else:
            logger.warning(
                'Password reset: no eligible account; no email will be sent '
                '(unknown email, inactive account or unusable password)'
            )
        return users


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the explicit local development settings bypass the external captcha.
        if settings.DEBUG and getattr(settings, 'LOCAL_DEVELOPMENT', False):
            self.fields.pop('captcha', None)

    captcha = ReCaptchaField(
    widget=ReCaptchaV3(
        attrs={
            'required_score':0.5, #aumenta el score de puntuacion para la deteccion de bots
            
        }
    )
)
    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as e:
            # Log completo del error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al validar el formulario de login: {e}')
            raise
    
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
    current_password = forms.CharField(label='Contraseña actual (para cambiar el correo)', required=False,
                                       widget=forms.PasswordInput)
    menu_color = forms.RegexField(regex=r'^#[0-9a-fA-F]{6}$',
        max_length=7,  # El valor hexadecimal del color es de 7 caracteres (#XXXXXX)
        widget=forms.TextInput(attrs={'type': 'color'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'avatar', 'position', 'menu_color']

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get('email') != self.instance.email and not self.instance.check_password(data.get('current_password', '')):
            self.add_error('current_password', 'Ingresá tu contraseña actual para cambiar el correo.')
        return data

    def clean_avatar(self):
        from django.core.files.uploadedfile import UploadedFile, SimpleUploadedFile
        from PIL import Image
        from io import BytesIO
        from uuid import uuid4
        upload = self.cleaned_data.get('avatar')
        if not isinstance(upload, UploadedFile):
            return upload
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError('El avatar no puede superar 2 MB.')
        try:
            upload.seek(0)
            with Image.open(upload) as picture:
                if picture.width * picture.height > 16000000:
                    raise ValueError('Oversized image')
                picture.thumbnail((512, 512))
                output = BytesIO()
                picture.convert('RGB').save(output, format='PNG')
            return SimpleUploadedFile(f'{uuid4().hex}.png', output.getvalue(), content_type='image/png')
        except (OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError('Seleccioná una imagen válida.')



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
