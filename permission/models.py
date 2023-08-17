from django.db import models
from login.models import CustomUser
from passbase.models import Contrasena

# Create your models here.
class ContraPermission(models.Model):
    user_id = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    contra_id = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, null=True)
    perm_active = models.BooleanField(default = True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    def Meta():
        verbose_name = "Permiso"
        verbose_name_plural= "Permisos"
        
    