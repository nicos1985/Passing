from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model
from django.db import connection

class Command(BaseCommand):
    help = 'Elimina todos los tenants y sus esquemas'

    def handle(self, *args, **kwargs):
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name='public')

        for tenant in tenants:
            schema_name = tenant.schema_name
            self.stdout.write(f"Borrando esquema: {schema_name}")

            # Eliminar el esquema asociado
            with connection.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')

            # Eliminar el tenant
            tenant.delete()

        self.stdout.write("Todos los tenants y esquemas han sido eliminados.")
