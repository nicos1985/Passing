from django.db import models
from login.models import CustomUser
from passbase.models import Contrasena

# Create your models here.
class ContraPermission(models.Model):
    user_id = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    contra_id = models.ForeignKey(Contrasena, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, blank=True)
    perm_active = models.BooleanField(default = True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Permiso"
        verbose_name_plural= "Permisos"

    def __str__(self):
        return str(self.user_id.username)
        

class PermissionRoles(models.Model):
    rol_name = models.CharField(max_length=60)
    contrasenas = models.ManyToManyField(Contrasena, related_name='roles')
    comment = models.CharField(max_length=200, blank=True)
    is_active=models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.rol_name
    
    def get_contrasenas(self):
        return self.contrasenas.all()
    
    def inactive(self):
        self.is_active = False
        self.save()
        return self.is_active

class UserRoles(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rol = models.ForeignKey(PermissionRoles, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'User: {self.user.username}, rol: {self.rol.rol_name}'