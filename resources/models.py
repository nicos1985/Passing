from django.db import models

from login.models import CustomUser

class Location(models.Model):
    name = models.CharField(max_length=120, unique=True, db_index=True, verbose_name='Nombre')
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='Descripcion')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Dueño')
    created = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Asset_Status(models.IntegerChoices):
    ACTIVE = 0, 'Activo'
    INACTIVE = 1, 'Inactivo'
    UNDER_REPAIR = 2, 'En Reparacion'
    BACK_UP = 3, 'Back up'
    
class Asset_Category(models.IntegerChoices):
    PC_OR_NOTEBOOK = 0, 'Pc o Notebook'
    MONITOR = 1, 'Monitor'
    PERIFERICAL = 2, 'Perifericos'
    STORAGE_UNIT = 3, 'Unidad de almacenamiento'
    INTERNAL_COMPONENTS = 4, 'Componentes internos'
    WIRE_AND_CONNECTORS = 5, 'Cables y conectores'
    PRINTER = 6, 'Impresoras'
    SERVER = 7, 'Servidores'
    SWITCH = 8, 'Switch'
    ROUTER = 9, 'Router'
    MODEM = 10, 'Modem'
    DOCUMENT = 11, 'Documento'
    SOFTWARE = 12, 'Software'
    SERVICE = 13, 'Servicio'
    MAIL = 14, 'Email'
    PASSWORD = 15, 'Password'
    KEY = 16, 'Key'
    OTHER = 17, 'Otro'

class Info_Class(models.IntegerChoices):
    PUBLIC = 0, 'Publica'
    INTERN = 1, 'Interna'
    CONFIDENTIAL = 2, 'Confidencial'



# Create your models here.
class InformationAssets(models.Model):
    name = models.CharField(max_length=120, unique=True, db_index=True, verbose_name='Nombre')
    code = models.CharField(max_length=60, unique=True, verbose_name='Codigo')
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='Descripcion')
    value = models.FloatField(blank=True, null=True, verbose_name='Valor monetario')
    acquisition_date = models.DateField(auto_now=True, verbose_name='Fecha de adquisicion')
    status = models.IntegerField(choices=Asset_Status.choices, default=Asset_Status.ACTIVE, verbose_name='Estado')
    category = models.IntegerField(choices=Asset_Category, verbose_name='Categoria')
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    serial_number = models.CharField(max_length=200, blank=True, null=True, verbose_name='Nro serie')
    information_classification = models.IntegerField(choices=Info_Class, verbose_name='Clasificacion de info')
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Dueño')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta():
        verbose_name = 'Activo de la informacion'
        verbose_name_plural = 'Activos de la informacion'
        
    



