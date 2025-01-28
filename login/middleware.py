from django.shortcuts import redirect
from django.contrib import messages

class TwoFactorAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si el usuario está autenticado y no ha completado 2FA
        if request.user.is_authenticated:
            if request.user.is_2fa_enabled and not request.session.get("is_2fa_verified", False):
                # Redirigir a la página de verificación 2FA
               
                if request.path not in ["/login/verify-2fa/", "/login/logout/", "/login/", "/login/generate_qr_code/"]:  # Excluir rutas específicas
                    messages.info(request, 'Para poder continuar debes completar el codigo de autenticacion.')
                    return redirect("verify_2fa")
        return self.get_response(request)
