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

