from django.db import models
from django.forms import model_to_dict
from django.db.models.signals import post_save, pre_save

from login.models import CustomUser

# Create your models here.
class SeccionContra(models.Model):

    nombre_seccion = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    
    def Meta():
        verbose_name = "Seccion"
        verbose_name_plural= "Secciones"
        
    def __str__(self):
        return self.nombre_seccion
    

class Contrasena(models.Model):
  

    nombre_contra = models.CharField(max_length=50, unique=True)
    seccion = models.ForeignKey(SeccionContra, on_delete=models.CASCADE)
    link = models.CharField(max_length=265)
    usuario = models.CharField(max_length=60)
    contraseña = models.CharField(max_length=60)
    actualizacion= models.IntegerField(default=30) #la contraseña pedirá cambio cada x dias de este campo
    info = models.CharField(max_length=260)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    
    def Meta():
        verbose_name = "Contraseña"
        verbose_name_plural= "Contraseñas"
        
    def __str__(self):
        return str(self.id)
    
    def toJSON(self):
        item = model_to_dict(self)
        return item
        
class LogData(models.Model):
    entidad = models.CharField(max_length=50)
    contraseña = models.IntegerField()
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default='')
    action = models.CharField(max_length=80, null = True)
    detail = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now=True)
    
    def Meta():
        verbose_name = "Log"
        
    def __str__(self):
        return self.contraseña
    
