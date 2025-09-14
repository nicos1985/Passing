from django.db import models
from django.db import connection
from accounts.models import CustomUser

class MultifactorChoices(models.IntegerChoices):
    DESACTIVADO = 0, 'Desactivado'
    ACTIVADO = 1, 'Activado'
    USER_CHOICE = 2, 'A eleccion del usuario'

def find_admin():
    su = CustomUser.objects.filter(is_superuser=True).order_by("id").first()
    return su.id if su else None

def get_domain_name(client=None):
    return str(connection.tenant)

class GlobalSettings(models.Model):
    multifactor_status = models.PositiveSmallIntegerField(choices=MultifactorChoices.choices, verbose_name='Politica 2do factor autenticacion', default=MultifactorChoices.DESACTIVADO)
    is_admin_dash_active = models.BooleanField(default=False, verbose_name='Dashboard administrador')
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name='Color de menu', default='#212629')
    set_admins = models.ManyToManyField(CustomUser, blank=True, verbose_name='Designar usuarios admin')
    company_name = models.CharField(max_length=20, null=True, blank=True, verbose_name='Nombre empresa')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)