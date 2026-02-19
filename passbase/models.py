"""Modelos de contraseñas privadas, secciones y auditorías para los tenants."""

import hashlib
import logging
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

logger = logging.getLogger(__name__)

# Create your models here.
class SeccionContra(models.Model):
    """Agrupa contraseñas en secciones temáticas y controla su estado."""

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
    """Registro cifrado de credenciales con metadatos de sección, propietario y hash."""

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
        """ Sobrescribe el método save para encriptar y generar un log. """

        # Encriptar datos si es necesario
        if isinstance(self.contraseña, str):
            self.contraseña = encrypt_data(self.contraseña)
        if isinstance(self.usuario, str):
            self.usuario = encrypt_data(self.usuario)
        
        # Verificar si la contraseña es nueva
        is_new = self._state.adding  # True si el objeto se está creando

        super().save(*args, **kwargs)

        # Si es una nueva contraseña, crear un log (redactando datos sensibles)
        logger.debug("Contrasena save: is_new=%s id=%s", is_new, getattr(self, 'id', None))
        if is_new:
            LogData.objects.create(
                entidad="Contrasena",
                password="[REDACTED]",
                contraseña=self.id,  # Guardamos el ID de la contraseña creada
                usuario=self.owner if self.owner else None,  # Usuario que creó la contraseña
                action="Create",
                detail=f"Nombre: {self.nombre_contra}, Seccion: {self.seccion}, Link: {self.link}, Info: {self.info}, owner: {self.owner}",
            )
        

    @classmethod
    def bulk_create_with_logs(cls, entries):
        """Inserta múltiples contraseñas y registra logs de creación en bloque."""
        objects = cls.objects.bulk_create(entries)

        logs = [
            LogData(
                entidad="Contrasena",
                password=obj.contraseña,
                contraseña=obj.id,
                usuario=obj.owner,
                action="Create",
                detail=f'''Nombre: {obj.nombre_contra}, 
                        Seccion: {obj.seccion}, 
                        Usuario: {obj.usuario}, 
                        Link: {obj.link}, 
                        Info: {obj.info},
                        owner: {obj.owner}'''
            ) 
            for obj in objects
        ]
        LogData.objects.bulk_create(logs)


    def get_decrypted_password(self):
        """Desencripta la contraseña almacenada y la devuelve en texto."""
        if not isinstance(self.contraseña, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.contraseña).__name__}")
        return decrypt_data(self.contraseña)
    
    def get_decrypted_user(self):
        """Devuelve el nombre de usuario original desencriptado."""
        if not isinstance(self.usuario, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.usuario).__name__}")
        return decrypt_data(self.usuario)
   
    def encrypt_password(self):
        """Vuelve a cifrar la contraseña actual para operaciones internas."""
        if not isinstance(self.contraseña, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.contraseña).__name__}")
        return encrypt_data(self.contraseña)
    
    def encrypt_user(self):
        """Vuelve a cifrar el campo usuario sin guardar el modelo."""
        if not isinstance(self.usuario, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.usuario).__name__}")
        return encrypt_data(self.usuario)

    def ratio_calculation(self, created_value):
        """Calcula un código de color que representa el estado de vencimiento."""
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
        """Recupera la fecha del último cambio de contraseña registrado."""
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
        """Retorna el color que indica si la contraseña está próxima a vencer."""
        created_value = self.last_pass_change()
        if created_value is None:
            return 'Sin data'
        return self.ratio_calculation(created_value)

    @property
    def last_change(self):
        """Diferencia en días desde la última modificación válida."""
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
        """Clasifica la fortaleza de la contraseña descifrada."""
        password = decrypt_data(self.contraseña)
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
    """Audita cambios sobre contraseñas y secciones guardando detalles cifrados."""
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
        """Cifra el valor en texto plano del campo password."""
        if not isinstance(self.password, (str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.password).__name__}")
        return encrypt_data(self.password)
    
    def get_decrypted_password(self):
        """Desencripta el password almacenado en este log."""
        if not isinstance(self.password, (bytes, str)):
            raise TypeError(f"Expected bytes or str, but got {type(self.password).__name__}")
        return decrypt_data(self.password)
    
    def get_encrypted_user(self):
        """Extrae el usuario cifrado embebido en el detalle del log."""
        try:
            usuario_encrypted_match = re.search(r'Usuario: (.+?),', self.detail)
            if usuario_encrypted_match:
                usuario_encrypted = usuario_encrypted_match.group(1).strip()
                
            else:
                usuario_encrypted = None
            return usuario_encrypted
        except Exception as e:
            logger.exception("Error extracting encrypted user: %s", e)
            return None

    def get_decrypted_user(self, usuario_encrypted):
        """Desencripta el usuario almacenado dentro de la cadena de detalle."""
        if usuario_encrypted is None:
            return None
        return decrypt_data(usuario_encrypted)