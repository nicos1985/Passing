"""Shared object access policy for the tenant password vault."""

from django.db.models import Q

from permission.models import ContraPermission
from .models import Contrasena


def accessible_credentials(user):
    """Personal credentials belong only to their owner, regardless of grants."""
    if not user.is_authenticated:
        return Contrasena.objects.none()
    allowed_ids = ContraPermission.objects.filter(
        user_id=user, permission=True, perm_active=True,
    ).values_list('contra_id', flat=True)
    return Contrasena.objects.filter(active=True).filter(
        Q(owner_id=user.pk) | Q(is_personal=False, pk__in=allowed_ids)
    )
