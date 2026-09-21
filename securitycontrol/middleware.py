from datetime import timedelta
from hashlib import sha256
import hmac
import ipaddress

from django.conf import settings
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin
from .models import RateLimitBucket


def allow_attempt(scope, identity, limit, seconds):
    now = timezone.now()
    window = int(now.timestamp()) // seconds
    # Neither submitted identities nor client addresses are stored in plaintext.
    key = hmac.new(settings.SECRET_KEY.encode(),
                   f'{scope}:{identity}:{window}'.encode(), sha256).hexdigest()
    RateLimitBucket.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(seconds=seconds * 2)})
    return bool(RateLimitBucket.objects.filter(key=key, count__lt=limit).update(count=F('count') + 1))


class SecurityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            return HttpResponse(status=400)
        if length > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            return HttpResponse('Solicitud demasiado grande (máximo 12 MB).', status=413)

    def process_view(self, request, view_func, args, kwargs):
        if request.method != 'POST':
            return None
        name = request.resolver_match.view_name
        login_views = {'login', 'two_factor:login'}
        limits = {
            'password_reset': (10, 3600), 'register': (10, 3600),
            'two_factor:setup': (30, 300), 'two_factor:recover': (10, 300),
        }
        if name not in login_views and name not in limits:
            return None
        scope = 'login' if name in login_views else name
        limit, seconds = (30, 300) if name in login_views else limits[name]
        # Trust a sanitized single-client header only from explicitly configured proxies.
        ip = request.META.get('REMOTE_ADDR', '')
        peer = ip or 'unix'
        if peer in getattr(settings, 'TRUSTED_PROXY_IPS', ()):
            try:
                ip = str(ipaddress.ip_address(request.META.get('HTTP_X_REAL_IP', '')))
            except ValueError:
                return HttpResponse('Encabezado de proxy inválido.', status=400)
        allowed = allow_attempt(scope + ':ip', ip, limit, seconds)
        identity = (request.POST.get('auth-username') or request.POST.get('email') or '').strip().casefold()
        if identity:
            allowed = allow_attempt(scope + ':account', identity[:254], 10, seconds) and allowed
        if not allowed:
            response = HttpResponse('Demasiados intentos. Esperá unos minutos antes de reintentar.', status=429)
            response['Retry-After'] = str(seconds)
            return response
        return None

    def process_response(self, request, response):
        if not request.path.startswith(settings.STATIC_URL):
            add_never_cache_headers(response)
        response['Referrer-Policy'] = 'same-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = (
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response
