
"""Funciones auxiliares para validar pertenencia del usuario al tenant actual."""

from django.db import connection
from django.db.models import Q
from client.models import Client
from accounts.models import CustomUser


def users_for_current_tenant():
    """Incluye membresías activas y usuarios heredados vinculados por client."""
    schema = getattr(connection, "schema_name", None)
    if not schema or schema == "public":
        return CustomUser.objects.none()
    client = Client.objects.filter(schema_name=schema).first()
    if client is None:
        return CustomUser.objects.none()
    return CustomUser.objects.filter(
        Q(client=client) | Q(memberships__client=client, memberships__is_active=True)
    ).exclude(memberships__client=client, memberships__is_active=False).distinct()

def user_belongs_to_current_tenant(user):
    """Usa el mismo criterio que el listado y las vistas de usuarios."""
    return users_for_current_tenant().filter(pk=user.pk).exists()
