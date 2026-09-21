"""Require a confirmed second factor before any application view is accessible."""

import logging

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django_otp import devices_for_user, verify_token
from two_factor.forms import AuthenticationTokenForm
from two_factor.utils import default_device
from two_factor.views import LoginView, SetupView

from .forms import CustomLoginForm

logger = logging.getLogger('django.security.mfa')


class MandatoryMFAMiddleware(MiddlewareMixin):
    public_views = {
        'login', 'two_factor:login', 'logout',
        'password_reset', 'password_reset_done', 'password_reset_confirm',
        'password_reset_complete',
    }
    enrollment_views = {'two_factor:setup', 'two_factor:qr'}

    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.view_name
        if name in self.public_views:
            return None
        # Django serves static assets this way in development only.
        if (settings.DEBUG and view_func.__module__ == 'django.views.static'
                and request.path.startswith(settings.STATIC_URL)):
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        device = default_device(request.user)
        if name in self.enrollment_views:
            if device:
                return redirect('two_factor:profile' if request.user.is_verified()
                                else 'two_factor:login')
            return None
        if not device:
            return redirect('two_factor:setup')
        if not request.user.is_verified():
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if request.resolver_match.app_name == 'admin' and not request.user.is_superuser:
            return HttpResponseForbidden('Solo superadministradores.')
        return None


class MandatoryLoginView(LoginView):
    # Keep the existing password + reCAPTCHA form. Recovery is administrator-only.
    form_list = (('auth', CustomLoginForm), ('token', AuthenticationTokenForm))
    condition_dict = {'token': LoginView.has_token_step}
    template_name = 'mfa/login.html'


@method_decorator(sensitive_post_parameters(), name='dispatch')
class MandatorySetupView(SetupView):
    template_name = 'mfa/setup.html'

    def done(self, form_list, **kwargs):
        # Serialize enrollment, including submissions from different browser tabs.
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=self.request.user.pk)
            if default_device(self.request.user):
                return redirect('two_factor:login')
            response = super().done(form_list, **kwargs)
            # Consume the enrollment code too, so it cannot be replayed at login.
            device = self.request.user.otp_device
            token_form = next(form for form in form_list if 'token' in form.cleaned_data)
            device.verify_token(token_form.cleaned_data['token'])
            logger.info('MFA enrolled: user_id=%s', self.request.user.pk)
            return response


class ResetAuthenticatorForm(forms.Form):
    password = forms.CharField(label='Tu contraseña de administrador', widget=forms.PasswordInput)
    token = forms.RegexField(
        regex=r'^\d{6}$', label='Código de tu autenticador',
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        device = default_device(self.user)
        # Verification uses django-otp's persistent throttling and replay protection.
        verified = device and verify_token(self.user, device.persistent_id, data['token'])
        if not verified or not self.user.check_password(data['password']):
            raise forms.ValidationError('Verificación incorrecta. Revisá los datos y esperá antes de reintentar.')
        return data


@never_cache
def security_profile(request):
    return render(request, 'mfa/profile.html')


@never_cache
@sensitive_post_parameters()
def reset_authenticator(request, user_id):
    if not request.user.is_superuser or not request.user.is_verified():
        return HttpResponseForbidden('Solo un superadministrador verificado puede recuperar el acceso.')
    target = get_object_or_404(get_user_model(), pk=user_id)
    if target.pk == request.user.pk:
        return HttpResponseForbidden('Otro superadministrador debe recuperar tu acceso.')
    form = ResetAuthenticatorForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=target.pk)
            for device in devices_for_user(target, confirmed=None):
                device.delete()
            # SESSION_ENGINE is the database backend in this project.
            for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
                if str(session.get_decoded().get('_auth_user_id')) == str(target.pk):
                    session.delete()
            logger.info('MFA reset by administrator: actor_id=%s user_id=%s',
                        request.user.pk, target.pk)
        return render(request, 'mfa/reset.html', {'target': target, 'completed': True})
    return render(request, 'mfa/reset.html', {'target': target, 'form': form})
