"""One authorization policy for every vault read and write."""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import Contrasena


def visible_credentials(user):
    if not user.is_authenticated or not user.is_active:
        return Contrasena.objects.none()
    return Contrasena.objects.filter(active=True).filter(
        Q(owner=user) | Q(is_personal=False, contrapermission__user_id=user,
                         contrapermission__permission='True', contrapermission__perm_active=True)
    ).distinct()


def superadmin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


class CredentialAccessMixin:
    def get_queryset(self):
        return visible_credentials(self.request.user)


class CredentialOwnerMixin(CredentialAccessMixin):
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)
