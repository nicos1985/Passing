
from django.db import connection
from client.models import Client
from accounts.models import TenantMembership

def user_belongs_to_current_tenant(user):
    schema = getattr(connection, "schema_name", None)
    client = Client.objects.get(schema_name=schema)
    return TenantMembership.objects.filter(
        user=user, client=client, is_active=True
    ).exists()
