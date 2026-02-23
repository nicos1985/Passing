from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.utils.translation import gettext_lazy as _

class Client(TenantMixin):
    client_name = models.CharField(max_length=255, verbose_name=_('Nombre de la Empresa'))
    business_sector = models.CharField(max_length=100, verbose_name=_('Rubro'))
    primary_mail = models.EmailField(unique=True, verbose_name=_('Correo Principal de la Cuenta'))
    plan = models.CharField(max_length=50, verbose_name=_('Plan de Servicio'), default='Free')
    created_superuser = models.IntegerField(default=0, verbose_name=_('Superuser creado')) # 0=False 1=True
    created = models.DateField(auto_now_add=True, verbose_name=_('Creado'))

    auto_create_schema = True  # Para crear un esquema automáticamente al crear un cliente.

class Domain(DomainMixin):
    pass

