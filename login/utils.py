
"""Funciones auxiliares para validar pertenencia del usuario al tenant actual."""

from django.db import connection
from client.models import Client
from accounts.models import TenantMembership

def user_belongs_to_current_tenant(user):
    """Verifica si un usuario del esquema público tiene membership activa en el tenant de la conexión."""
    schema = getattr(connection, "schema_name", None)
    client = Client.objects.get(schema_name=schema)
    return TenantMembership.objects.filter(
        user=user, client=client, is_active=True
    ).exists()
