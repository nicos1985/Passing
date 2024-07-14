from django.utils import timezone
from datetime import datetime
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
    actualizacion= models.PositiveSmallIntegerField(default=30) #la contraseña pedirá cambio cada x dias de este campo
    info = models.CharField(max_length=260)
    file = models.FileField(blank=True, null=True, upload_to='contra_files/')
    is_personal = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, blank=True, null=True)
    
    def Meta():
        verbose_name = "Contraseña"
        verbose_name_plural= "Contraseñas"
        
    def __str__(self):
        return str(self.id)
    
    def toJSON(self):
        item = model_to_dict(self)
        return item

    
    def ratio_calculation(self, created_value):
        fecha_hoy = timezone.now()
        dias_actualizacion = self.actualizacion
        dias_transcurridos = (fecha_hoy - created_value).days
        dias_faltantes = dias_actualizacion - dias_transcurridos
        
        try:
            ratio = dias_faltantes / dias_actualizacion
        except ZeroDivisionError:
            ratio = 0
        
        if ratio <= 0:
            return 'danger'
        elif 0.01 < ratio <= 0.09:
            return 'warning'
        else:
            return 'success'

    def last_pass_change(self):
        log_data_change_pass = LogData.objects.filter(contraseña=self.id, action='change pass').order_by('-created')[:1]
        
        if log_data_change_pass.exists():
            log_data_objeto = log_data_change_pass.first()
            created_value = log_data_objeto.created
            return created_value
        else:
            log_data_created = LogData.objects.filter(contraseña=self.id, action='Create').order_by('-created')[:1]
            
            if log_data_created.exists():
                log_data_objeto = log_data_created.first()
                created_value = log_data_objeto.created
                return created_value
            else:
                return None

    @property
    def flag(self):
        created_value = self.last_pass_change()
        if created_value is None:
            return 'Sin data'
        return self.ratio_calculation(created_value)

    @property
    def last_change(self):
        created_value = self.last_pass_change()
        if created_value is None:
            return 'Sin data'
        if isinstance(created_value, str):
            created_value = datetime.fromisoformat(created_value)
        fecha_hoy = timezone.now()
        dias_transcurridos = (fecha_hoy - created_value).days
        return dias_transcurridos
        
class LogData(models.Model):
    entidad = models.CharField(max_length=50)
    contraseña = models.IntegerField()
    password = models.CharField(max_length=50, null=True, blank=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default='')
    action = models.CharField(max_length=80, null = True)
    detail = models.CharField(max_length=1000)
    created = models.DateTimeField(auto_now=True)
    
    def Meta():
        verbose_name = "Log"
        
    def __str__(self):
        return str(self.contraseña)
    
