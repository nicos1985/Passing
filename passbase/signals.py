from django.db.models.signals import post_save, pre_save

from .models import Contrasena, HContrasena

from django.dispatch import receiver

# @receiver(pre_save, sender = Contrasena)
# def pre_save_contrasena(sender,**kwargs):
#     object = Contrasena.objects.get()

