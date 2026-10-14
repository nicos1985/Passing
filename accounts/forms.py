from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3


CAPTCHA_ERRORS = {
    'captcha_invalid': 'No pudimos verificar la solicitud. Intentá nuevamente.',
    'captcha_error': 'No pudimos verificar la solicitud. Intentá nuevamente.',
}

class HubReCaptchaField(ReCaptchaField):
    """Trata fallas de la verificación externa como un formulario inválido."""

    def validate(self, value):
        try:
            super().validate(value)
        except (OSError, ValueError, KeyError) as exc:
            raise ValidationError(self.error_messages['captcha_error'], code='captcha_error') from exc


class HubLoginForm(forms.Form):
    """Formulario público para autenticarse en el hub con credenciales o email."""

    identity = forms.CharField(label="Email o usuario", max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
    next = forms.CharField(widget=forms.HiddenInput, required=False)
    captcha = HubReCaptchaField(
        widget=ReCaptchaV3(action='hub_login', attrs={'required_score': 0.5}),
        error_messages=CAPTCHA_ERRORS,
    )


class HubPasswordResetForm(PasswordResetForm):
    """Recuperación pública protegida con reCAPTCHA invisible."""

    captcha = HubReCaptchaField(
        widget=ReCaptchaV3(action='password_recovery', attrs={'required_score': 0.5}),
        error_messages=CAPTCHA_ERRORS,
    )
