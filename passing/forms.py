
from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3
from client.models import Client

class EmailConfigForm(forms.Form):
    
    email_host = forms.CharField(label='Servidor de email', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email_port = forms.IntegerField(label='Puerto de smtp', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    email_use_tls = forms.BooleanField(required=False, label='Uso tls', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    email_host_user = forms.EmailField(label='mail de salida', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    email_host_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='password')




class ClientRegisterForm(forms.ModelForm):
    captcha = ReCaptchaField(
        widget=ReCaptchaV3(
            attrs={
                'required_score': 0.8,  # Aumenta el score de puntuación para la detección de bots
            }
        )
    )

    class Meta:
        model = Client
        fields = ['client_name', 'business_sector', 'primary_mail', 'plan']
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_sector': forms.TextInput(attrs={'class': 'form-control'}),
            'primary_mail': forms.EmailInput(attrs={'class': 'form-control'}),
            'plan': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'client_name': 'Nombre de la Empresa',
            'business_sector': 'Rubro',
            'primary_mail': 'Correo Principal de la Cuenta',
            'plan': 'Plan de Servicio',
        }