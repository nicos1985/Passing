"""Shared object access policy for the tenant password vault."""

from django.db.models import Q

from permission.models import ContraPermission
from .models import Contrasena


def accessible_credentials(user):
    """Owners retain access; other users need an explicit active grant."""
    if not user.is_authenticated:
        return Contrasena.objects.none()
    allowed_ids = ContraPermission.objects.filter(
        user_id=user, permission=True, perm_active=True,
    ).values_list('contra_id', flat=True)
    return Contrasena.objects.filter(active=True).filter(
        Q(owner_id=user.pk) | Q(pk__in=allowed_ids)
    )
