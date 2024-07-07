from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    avatar = models.ImageField(blank=True, null=True, upload_to='static/')
    position = models.CharField(max_length=80,null=True, verbose_name='Puesto')
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Domicilio')
    tel_number=models.CharField(max_length=13, blank=True, null=True, verbose_name='Nro Telefono')
    admission_date = models.DateField(blank=True, null=True, verbose_name='Fecha Ingreso')
    departure_date = models.DateField(blank=True, null=True, verbose_name='Fecha Egreso')



     