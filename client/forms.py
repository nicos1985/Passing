from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3
from client.models import Client

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