from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Client(TenantMixin):
    client_name = models.CharField(max_length=255, verbose_name='Nombre de la Empresa')
    business_sector = models.CharField(max_length=100, verbose_name='Rubro')
    primary_mail = models.EmailField(unique=True, verbose_name='Correo Principal de la Cuenta')
    plan = models.CharField(max_length=50, verbose_name='Plan de Servicio', default='Free')
    created_superuser = models.IntegerField(default=0, verbose_name='Superuser creado') # 0=False 1=True
    created = models.DateField(auto_now_add=True)

    auto_create_schema = True  # Para crear un esquema automáticamente al crear un cliente.

class Domain(DomainMixin):
    pass

