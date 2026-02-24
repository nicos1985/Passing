from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.db import connection
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
        if schema == "public":
            return self.get_response(request)

        # Si el usuario está autenticado y no ha completado 2FA
        if request.user.is_authenticated:
            try:
                is_enabled = getattr(request.user, "is_2fa_enabled", None)
                otp_present = bool(getattr(request.user, "otp_secret", None))
                session_verified = bool(request.session.get("is_2fa_verified", False))
                logger.debug(
                    "TwoFactorAuthMiddleware: user=%s is_2fa_enabled=%s otp_present=%s session_is_2fa_verified=%s path=%s",
                    getattr(request.user, "pk", None), is_enabled, otp_present, session_verified, request.path,
                )
            except Exception:
                logger.exception("Error leyendo atributos de usuario en TwoFactorAuthMiddleware")

            if is_enabled and not request.session.get("is_2fa_verified", False):
                # Redirigir a la página de verificación 2FA
                if request.path not in [
                    "/login/verify-2fa/",
                    "/login/logout/",
                    "/login/",
                    "/login/generate_qr_code/",
                ]:  # Excluir rutas específicas
                    messages.info(request, "Para poder continuar debes completar el codigo de autenticacion.")
                    try:
                        # Intentá resolver usando el urlconf activo para la request (tenant vs public)
                        urlconf = getattr(request, "urlconf", None)
                        verify_url = reverse("verify_2fa", urlconf=urlconf)
                    except Exception:
                        # Fallback a ruta absoluta conocida
                        verify_url = "/login/verify-2fa/"

                    return redirect(verify_url)

        return self.get_response(request)
