from allauth.account.adapter import DefaultAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden

from .models import AuthEvent
from .utils import get_ip, get_ua

User = get_user_model()

class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # sin registro por allauth

class SocialAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # Si ya existe el SocialAccount, allauth seguirá normal
        if sociallogin.is_existing:
            return

        email = (sociallogin.user and sociallogin.user.email) or \
                sociallogin.account.extra_data.get("email")
        if not email:
            AuthEvent.objects.create(
                user=None, client=None, event=AuthEvent.LOGIN_GOOGLE, success=False,
                provider="google", ip=get_ip(request), ua=get_ua(request),
                meta={"reason": "no_email_from_google"}
            )
            raise ImmediateHttpResponse(HttpResponseForbidden("Google no devolvió email."))

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            AuthEvent.objects.create(
                user=None, client=None, event=AuthEvent.LOGIN_GOOGLE, success=False,
                provider="google", ip=get_ip(request), ua=get_ua(request),
                meta={"reason": "user_not_found", "email": email}
            )
            raise ImmediateHttpResponse(HttpResponseForbidden("No tienes cuenta en Passing."))

        # Vincular este sociallogin al usuario existente y continuar
        sociallogin.connect(request, user)
        AuthEvent.objects.create(
            user=user, client=None, event=AuthEvent.LOGIN_GOOGLE, success=True,
            provider="google", ip=get_ip(request), ua=get_ua(request),
            meta={"stage": "hub_pre_login"}
        )
