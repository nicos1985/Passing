from functools import wraps
from django.http import HttpResponseForbidden
from django_tenants.utils import get_tenant
from .models import TenantMembership

def require_tenant_membership(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Autenticación requerida.")
        tenant = get_tenant()
        ok = TenantMembership.objects.filter(
            user=request.user, client_id=tenant.id, is_active=True
        ).exists()
        if not ok:
            return HttpResponseForbidden("No tienes acceso a este espacio.")
        return view(request, *args, **kwargs)
    return _wrapped
