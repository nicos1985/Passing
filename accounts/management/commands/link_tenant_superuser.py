"""Vincula un superusuario creado desde la consola con un tenant existente."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, TenantMembership, TenantSettings
from client.models import Client


class Command(BaseCommand):
    help = 'Vincula un superusuario existente con un tenant; no recibe contraseñas.'

    def add_arguments(self, parser):
        parser.add_argument('schema_name')
        parser.add_argument('username')

    @transaction.atomic
    def handle(self, schema_name, username, **options):
        client = Client.objects.filter(schema_name=schema_name).first()
        if client is None or schema_name == 'public':
            raise CommandError('Tenant no encontrado.')
        user = CustomUser.objects.filter(username=username, is_superuser=True, is_staff=True, is_active=True).first()
        if user is None:
            raise CommandError('Se requiere un superusuario activo creado con createsuperuser.')
        if user.client_id not in (None, client.pk):
            raise CommandError('El usuario ya pertenece a otro tenant.')
        if CustomUser.objects.filter(client=client, is_superuser=True).exclude(pk=user.pk).exists():
            raise CommandError('El tenant ya tiene un superusuario.')
        user.client = client
        user.save(update_fields=['client'])
        TenantMembership.objects.update_or_create(user=user, client=client, defaults={'is_active': True})
        TenantSettings.objects.get_or_create(client=client)
        client.created_superuser = 1
        client.save(update_fields=['created_superuser'])
        self.stdout.write(self.style.SUCCESS('Superusuario vinculado al tenant.'))
