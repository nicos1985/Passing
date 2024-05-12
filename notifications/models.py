from django.db import models
from passbase.models import Contrasena
from login.models import CustomUser

class UserNotifications(models.Model):
    """Se encarga de gestionar el modelo de notificaciones a usuarios que 
    no sean ni admin ni staff solo van a ser notificaciones si acciones"""

    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    id_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    type_notification = models.CharField(max_length=50)
    comment = models.CharField(max_length=60)
    viewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now=True)

    def Meta():
        verbose_name = "Notificaciones a usuario"
        

class AdminNotification(models.Model):
    """Se encarga de gestionar el modelo de notificaciones a admins y staff.
    pueden realizar acciones sobre estas notificaciones."""
    USER = (
        (0, 'admin'),
        (1, 'staff')
    )

    id_contrasena = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    id_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    type_notification = models.CharField(max_length=50)
    type_user = models.IntegerChoices(default=0, choices=USER)
    action = models.CharField(max_length=50)
    comment = models.CharField(max_length=60)
    viewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now=True)

    def Meta():
        verbose_name = "Notificaciones a admin"