"""Modelos y helpers del login tenant: settings globales y helpers asociados."""

from django.db import models
from django.db import connection
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _

class MultifactorChoices(models.IntegerChoices):
    """Opciones que describen el estado de habilitación del segundo factor."""
    DESACTIVADO = 0, _('Desactivado')
    ACTIVADO = 1, _('Activado')
    USER_CHOICE = 2, _('A eleccion del usuario')

def find_admin():
    """Devuelve el ID del primer superusuario público."""
    su = CustomUser.objects.filter(is_superuser=True).order_by("id").first()
    return su.id if su else None

def get_domain_name(client=None):
    """Helper que expone el nombre del tenant actual según la conexión."""
    return str(connection.tenant)

class GlobalSettings(models.Model):
    """Configuraciones globales por tenant: 2FA en masa, dashboard y administradores."""
    multifactor_status = models.PositiveSmallIntegerField(choices=MultifactorChoices.choices, verbose_name=_('Politica 2do factor autenticacion'), default=MultifactorChoices.DESACTIVADO)
    is_admin_dash_active = models.BooleanField(default=False, verbose_name=_('Dashboard administrador'))
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name=_('Color de menu'), default='#212629')
    set_admins = models.ManyToManyField(CustomUser, blank=True, verbose_name=_('Designar usuarios admin'))
    company_name = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('Nombre empresa'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))
    created_at = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Actualizado'))