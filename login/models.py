from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import transaction
from client.models import Client
from django.db import connection


class CustomUser(AbstractUser):
    avatar = models.ImageField(blank=True, null=True, upload_to='avatars/')
    position = models.CharField(max_length=80,null=True, verbose_name='Puesto')
    email = models.EmailField(unique=True)
    documento = models.CharField(max_length=8, blank=True, null=True, verbose_name='documento')
    birth_date = models.DateField(blank=True, null=True, verbose_name='Fecha Nacimiento')
    address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Domicilio')
    tel_number=models.CharField(max_length=13, blank=True, null=True, verbose_name='Nro Telefono')
    admission_date = models.DateField(blank=True, null=True, verbose_name='Fecha Ingreso')
    departure_date = models.DateField(blank=True, null=True, verbose_name='Fecha Egreso')
    departure_motive = models.CharField(max_length=1000,blank=True, null=True, verbose_name='Motivo de baja')
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name='Color de menu', default='#212629')
    assigned_role = models.ForeignKey('permission.PermissionRoles', on_delete=models.CASCADE, verbose_name='Rol asignado', default=1)
    client = models.ForeignKey('client.Client', on_delete=models.CASCADE, null=True, blank=True)
    otp_secret = models.CharField(max_length=32, blank=True, null=True)
    is_2fa_enabled = models.BooleanField(default=False)


    def formatted_birth_date(self):
        return self.birth_date.strftime('%Y-%m-%d') if self.birth_date else ''
    
    def formatted_admission_date(self):
        return self.admission_date.strftime('%Y-%m-%d') if self.admission_date else ''
    
    def formatted_departure_date(self):
        return self.departure_date.strftime('%Y-%m-%d') if self.departure_date else ''
    

    def inactivate(self):
        try:
            with transaction.atomic():
                self.is_active = False
                self.save(update_fields=['is_active'])
            message = f'Se inactivó el usuario <strong>{self.username}</strong> con éxito. Estado: {self.is_active}'
        except Exception as e:
            message = f'No se pudo inactivar el usuario <strong>{self.username}</strong>. Error: {str(e)}'
        return message
    
    
    def activate(self):
        try:
            self.is_active = True
            self.save()
            message = f'Se activó el usuario <strong>{self.username}</strong> con éxito.'
        except Exception as e:
            message = f'No se pudo activar el usuario <strong>{self.username}</strong>. Error: {str(e)}'
        return message
    
    def has_otp_secret(self):
        if self.otp_secret:
            return True
        else:
            return False
        

class MultifactorChoices(models.IntegerChoices):
   DESACTIVADO = 0, 'Desactivado'
   ACTIVADO = 1, 'Activado'
   USER_CHOICE = 2, 'A eleccion del usuario'

def find_admin():
    superuser = CustomUser.objects.filter(is_superuser=True).order_by(id).first()
    return superuser.id

def get_domain_name(client):
    tenant = connection.tenant
    current_domain = tenant
    return str(current_domain)

class GlobalSettings(models.Model):
    multifactor_status = models.PositiveSmallIntegerField(choices=MultifactorChoices.choices, verbose_name='Politica 2do factor autenticacion', default=MultifactorChoices.DESACTIVADO)
    is_admin_dash_active = models.BooleanField(default=False, verbose_name='Dashboard administrador')
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name='Color de menu', default='#212629')
    set_admins = models.ManyToManyField(CustomUser, blank=True, null=True, verbose_name='Designar usuarios admin')
    company_name = models.CharField(max_length=20, null=True, blank=True, verbose_name='Nombre empresa')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)