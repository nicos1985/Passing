"""Modelos que registran alertas sobre contraseñas para usuarios y administradores."""

from django.db import models
from passbase.models import Contrasena
from login.models import CustomUser


class UserNotifications(models.Model):
    """Notificaciones que se envían a usuarios comunes cuando falta acción."""

    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    id_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    type_notification = models.CharField(max_length=150)
    comment = models.CharField(max_length=150)
    viewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notificaciones a usuario"


class UserType(models.IntegerChoices):
    """Tipos de usuario que pueden recibir notificaciones administrativas."""

    STAFF = 0, 'Staff'
    ADMIN = 1, 'Admin'


class AdminNotification(models.Model):
    """Registro de solicitudes enviadas a admins o staff sobre contraseñas."""

    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    id_user = models.CharField(max_length=50)
    id_user_share = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    type_notification = models.CharField(max_length=50)
    type_user = models.IntegerField(choices=UserType.choices, default=UserType.ADMIN)
    action = models.CharField(max_length=50)
    comment = models.CharField(max_length=60)
    viewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notificaciones a admin"