"""Modelos que registran alertas sobre contraseñas para usuarios y administradores."""

from django.db import models
from django.conf import settings
from passbase.models import Contrasena
from login.models import CustomUser
from django.utils.translation import gettext_lazy as _


class UserNotifications(models.Model):
    """Notificaciones que se envían a usuarios comunes cuando falta acción."""
    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE, verbose_name=_('Contraseña'))
    id_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name=_('Usuario'))
    type_notification = models.CharField(max_length=150, verbose_name=_('Tipo de notificación'))
    comment = models.CharField(max_length=150, verbose_name=_('Comentario'))
    viewed = models.BooleanField(default=False, verbose_name=_('Visto'))
    created = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))

    class Meta:
        verbose_name = _("Notificaciones a usuario")


class UserType(models.IntegerChoices):
    """Tipos de usuario que pueden recibir notificaciones administrativas."""

    STAFF = 0, _('Staff')
    ADMIN = 1, _('Admin')


class AdminNotification(models.Model):
    """Registro de solicitudes enviadas a admins o staff sobre contraseñas."""

    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE, verbose_name=_('Contraseña'))
    id_user = models.CharField(max_length=50, verbose_name=_('Usuario'))
    id_user_share = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name=_('Usuario compartido'))
    type_notification = models.CharField(max_length=50, verbose_name=_('Tipo de notificación'))
    type_user = models.IntegerField(choices=UserType.choices, default=UserType.ADMIN, verbose_name=_('Tipo de usuario'))
    action = models.CharField(max_length=50, verbose_name=_('Acción'))
    comment = models.CharField(max_length=60, verbose_name=_('Comentario'))
    viewed = models.BooleanField(default=False, verbose_name=_('Visto'))
    created = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))

    class Meta:
        verbose_name = _("Notificaciones a admin")
    ordering = ('viewed',)


class InboxNotification(models.Model):
    """Aviso interno breve, individual e independiente del canal externo."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inbox_notifications')
    category = models.CharField(max_length=32)
    source_id = models.BigIntegerField()
    event = models.CharField(max_length=24)
    title = models.CharField(max_length=120)
    target_path = models.CharField(max_length=240, blank=True)
    channels = models.CharField(max_length=32, blank=True)
    viewed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [models.UniqueConstraint(
            fields=['user', 'category', 'source_id', 'event'], name='inbox_notification_once',
        )]
