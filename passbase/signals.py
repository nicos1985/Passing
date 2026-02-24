"""Señales del app `passbase`.

Este fichero registra receptores de señales para auditar cambios en contraseñas.
Actualmente contiene los import básicos y está preparado para añadir receivers.
"""

from django.db.models.signals import post_save, pre_save

from .models import Contrasena

from django.dispatch import receiver


# Placeholder: register signal handlers here when needed.


