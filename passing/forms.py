
from django import forms

class EmailConfigForm(forms.Form):
    
    email_host = forms.CharField(label='Servidor de email', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email_port = forms.IntegerField(label='Puerto de smtp', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    email_use_tls = forms.BooleanField(required=False, label='Uso tls', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    email_host_user = forms.EmailField(label='mail de salida', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    email_host_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='password')