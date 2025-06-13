from django.db.models.signals import post_save, pre_save

from .models import Contrasena, HContrasena

from django.dispatch import receiver


