from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden

from .models import AuthEvent, TenantMembership
from .utils import get_ip, get_ua

User = get_user_model()

class AccountAdapter(DefaultAccountAdapter):
    """Impide registros nuevos desde allauth y deja solo el login."""

    def is_open_for_signup(self, request):
        return False  # sin registro por allauth

class SocialAdapter(DefaultSocialAccountAdapter):
    """Vincula logins de Google con usuarios existentes y audita fallos."""

    def pre_social_login(self, request, sociallogin):
        def deny(reason, message):
            AuthEvent.objects.create(
                user=None, client=None, event=AuthEvent.LOGIN_GOOGLE, success=False,
                provider="google", ip=get_ip(request), ua=get_ua(request),
                meta={"reason": reason},
            )
            raise ImmediateHttpResponse(HttpResponseForbidden(message))

        def eligible_memberships(user, autolink=False):
            memberships = TenantMembership.objects.filter(
                user=user, is_active=True, client__settings__is_active=True,
                client__settings__sso_google_enabled=True,
            )
            if autolink:
                memberships = memberships.filter(client__settings__sso_autolink_by_email=True)
            return memberships

        if sociallogin.is_existing:
            user = sociallogin.user
            if not user.is_active or not eligible_memberships(user).exists():
                deny("google_access_disabled", "El acceso con Google no está habilitado para tu cuenta.")
            return

        verified_emails = {
            address.email.casefold() for address in sociallogin.email_addresses
            if address.verified and address.email
        }
        email = (sociallogin.user and sociallogin.user.email) or sociallogin.account.extra_data.get("email")
        if not email or email.casefold() not in verified_emails:
            deny("unverified_email", "Google no confirmó el correo de esta cuenta.")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            deny("user_not_found", "No tienes cuenta en Passing.")
        except User.MultipleObjectsReturned:
            deny("ambiguous_email", "Contactá al administrador para revisar tu cuenta.")

        if not user.is_active:
            deny("inactive_user", "Tu cuenta está pendiente de activación.")
        if not eligible_memberships(user, autolink=True).exists():
            deny("google_access_disabled", "El acceso con Google no está habilitado para tu cuenta.")

        sociallogin.connect(request, user)
        AuthEvent.objects.create(
            user=user, client=None, event=AuthEvent.LOGIN_GOOGLE, success=True,
            provider="google", ip=get_ip(request), ua=get_ua(request),
            meta={"stage": "hub_pre_login"},
        )
