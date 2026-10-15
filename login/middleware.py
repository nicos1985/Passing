from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.db import connection
from django.conf import settings
from accounts.models import MultiFactorStatus, TenantSettings
import logging


logger = logging.getLogger(__name__)


class TwoFactorAuthMiddleware:
    """Middleware que obliga al usuario a completar 2FA antes de continuar.

    Añadí trazas para depurar por qué un usuario con `is_2fa_enabled=False`
    podría ser redirigido inesperadamente.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only enforce 2FA for tenant schemas (skip public hub to avoid invalid redirects)
        schema = getattr(connection, "schema_name", None)
        if not schema or schema == "public":
            return self.get_response(request)
        if request.path.startswith(settings.STATIC_URL):
            return self.get_response(request)

        # Si el usuario está autenticado y no ha completado 2FA
        if request.user.is_authenticated:
            tenant = getattr(request, 'tenant', None) or getattr(connection, 'tenant', None)
            policy = TenantSettings.for_client(tenant)
            status = policy.multifactor_status if policy else MultiFactorStatus.DISABLED
            required = status == MultiFactorStatus.REQUIRED
            enabled = required or (status == MultiFactorStatus.OPTIONAL and request.user.is_2fa_enabled)
            verified = (
                request.session.get('is_2fa_verified') is True
                and request.session.get('twofa_verified_user_id') == request.user.pk
                and request.session.get('twofa_verified_client_id') == getattr(tenant, 'pk', None)
            )
            if enabled and not verified:
                urlconf = getattr(request, 'urlconf', None)
                allowed = {reverse(name, urlconf=urlconf) for name in ('verify_2fa', 'show-qr-code-2fa', 'logout')}
                if request.path not in allowed:
                    messages.info(request, 'Completá la verificación en dos pasos para continuar.')
                    target = 'show-qr-code-2fa' if not request.user.otp_secret or (required and not request.user.is_2fa_enabled) else 'verify_2fa'
                    return redirect(reverse(target, urlconf=urlconf))

        return self.get_response(request)
