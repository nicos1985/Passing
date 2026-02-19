from django import forms

class HubLoginForm(forms.Form):
    """Formulario público para autenticarse en el hub con credenciales o email."""

    identity = forms.CharField(label="Email o usuario", max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
    next = forms.CharField(widget=forms.HiddenInput, required=False)
