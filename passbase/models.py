import hashlib
from django.utils import timezone
from datetime import datetime
from django.db import models
from django.forms import model_to_dict
from django.db.models.signals import post_save, pre_save
import re
from cryptography.fernet import Fernet

from login.models import CustomUser
from passbase.crypto import decrypt_data, encrypt_data
from passing import settings

# Create your models here.
class SeccionContra(models.Model):

    nombre_seccion = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Seccion"
        verbose_name_plural= "Secciones"
        
    def __str__(self):
        return self.nombre_seccion
    

class Contrasena(models.Model):
  

    nombre_contra = models.CharField(max_length=255, unique=True)
    seccion = models.ForeignKey(SeccionContra, on_delete=models.CASCADE)
    link = models.CharField(max_length=265)
    usuario = models.CharField(max_length=255)
    contraseña = models.CharField(max_length=500)
    actualizacion= models.PositiveSmallIntegerField(default=30) #la contraseña pedirá cambio cada x dias de este campo
    info = models.CharField(max_length=260)
    file = models.FileField(blank=True, null=True, upload_to='contra_files/')
    is_personal = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, blank=True, null=True)
    hash = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        verbose_name = "Contraseña"
        verbose_name_plural= "Contraseñas"
        
    def __str__(self):
        return str(self.id)
    
    def toJSON(self):
        item = model_to_dict(self)
        return item
    
    def save(self, *args, **kwargs):
        # # Aseguramos que usuario y contraseña sean strings
        # usuario = self.usuario if isinstance(self.usuario, str) else self.usuario.decode('utf-8')
        # print(f'usuario: {usuario}')
        # contraseña = self.contraseña if isinstance(self.contraseña, str) else self.contraseña.decode('utf-8')
        # print(f'contraseña: {contraseña}')
        # # Concatenamos las cadenas de texto y generamos el hash
        # self.hash = hashlib.sha256((usuario + contraseña).encode('utf-8')).hexdigest()
        # # Encriptar la contraseña antes de guardarla
        if isinstance(self.contraseña, str):
            self.contraseña = encrypt_data(self.contraseña)
        if isinstance(self.usuario, str):
            self.usuario = encrypt_data(self.usuario)
        super().save(*args, **kwargs)

    def get_decrypted_password(self):
        if not isinstance(self.contraseña, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.contraseña).__name__}")
        return decrypt_data(self.contraseña)
    
    def get_decrypted_user(self):
        if not isinstance(self.usuario, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.usuario).__name__}")
        return decrypt_data(self.usuario)
   
    def encrypt_password(self):
        if not isinstance(self.contraseña, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.contraseña).__name__}")
        return encrypt_data(self.contraseña)
    
    def encrypt_user(self):
        if not isinstance(self.usuario, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.usuario).__name__}")
        return encrypt_data(self.usuario)

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
            return '#FF7367' #Contraseña Vencida
        elif 0.01 < ratio <= 0.09:
            return '#FFE682' #Contraseña por vencer
        else:
            return '#7CFF6D' #Contraseña en plazo

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
    
    @property
    def password_strength(self):
        password = self.contraseña
        length = len(password)

        # Check for presence of different character types
        has_upper = re.search(r'[A-Z]', password) is not None
        has_lower = re.search(r'[a-z]', password) is not None
        has_digit = re.search(r'\d', password) is not None
        has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', password) is not None

        # Evaluate strength based on the criteria
        strength = 0

        if length >= 8:
            strength += 1
        if length >= 12:
            strength += 1
        if has_upper:
            strength += 1
        if has_lower:
            strength += 1
        if has_digit:
            strength += 1
        if has_special:
            strength += 1

        if strength <= 2:
            return 'weak'
        elif 3 <= strength <= 4:
            return 'moderate'
        elif strength >= 5:
            return 'strong'
        
class LogData(models.Model):
    entidad = models.CharField(max_length=50)
    contraseña = models.IntegerField()
    password = models.CharField(max_length=500, blank=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default='')
    action = models.CharField(max_length=80, blank=True)
    detail = models.CharField(max_length=2000)
    created = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Log"
        
    def __str__(self):
        return str(self.contraseña)
    
    def encrypt_password(self):
        if not isinstance(self.password, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.password).__name__}")
        return encrypt_data(self.password)
    
    def get_decrypted_password(self):
        if not isinstance(self.password, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.password).__name__}")
        return decrypt_data(self.password)
    
    def get_encrypted_user(self):
        try:
            usuario_encrypted_match = re.search(r'Usuario: (.+?),', self.detail)
            if usuario_encrypted_match:
                usuario_encrypted = usuario_encrypted_match.group(1).strip()
                
            else:
                usuario_encrypted = None
            return usuario_encrypted
        except Exception as e:
            print(f"Error extracting encrypted user: {e}")
            return None

    def get_decrypted_user(self, usuario_encrypted):
            if usuario_encrypted is None:
                return None
            else:
                return decrypt_data(usuario_encrypted)