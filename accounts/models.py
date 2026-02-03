from django.db import models
# accounts/models.py (PUBLIC)
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.db import connection


def avatar_upload_to(instance, filename):
    """Place uploaded avatars under a tenant-prefixed folder.

    Examples:
      <schema>/avatars/filename.jpg
      public/avatars/filename.jpg  (fallback)
    """
    try:
        tenant = getattr(connection, "tenant", None)
        schema_name = getattr(tenant, "schema_name", None) if tenant is not None else getattr(connection, "schema_name", None)
        if not schema_name:
            schema_name = "public"
        return f"{schema_name}/avatars/{filename}"
    except Exception:
        return f"public/avatars/{filename}"


CLIENT_FK = 'client.Client'   

class CustomUser(AbstractUser):
    avatar = models.ImageField(blank=True, null=True, upload_to=avatar_upload_to)
    position = models.CharField(max_length=80, null=True, verbose_name='Puesto')
    email = models.EmailField(unique=True)
    documento = models.CharField(max_length=8, blank=True, null=True, verbose_name='documento')
    birth_date = models.DateField(blank=True, null=True, verbose_name='Fecha Nacimiento')
    address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Domicilio')
    tel_number = models.CharField(max_length=13, blank=True, null=True, verbose_name='Nro Telefono')
    admission_date = models.DateField(blank=True, null=True, verbose_name='Fecha Ingreso')
    departure_date = models.DateField(blank=True, null=True, verbose_name='Fecha Egreso')
    departure_motive = models.CharField(max_length=1000, blank=True, null=True, verbose_name='Motivo de baja')
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name='Color de menu', default='#212629')

    # ⚠️ OJO: 'assigned_role' NO puede ser FK a un modelo TENANT desde PUBLIC. Lo resolvemos en Fase 2.
    # De momento damos un stub para no romper templates/vistas que accedan a user.assigned_role.
    @property
    def assigned_role(self):
        """
        Devuelve el `PermissionRoles` asignado al usuario mediante el modelo `UserRoles`.
        Como `CustomUser` está en PUBLIC y `PermissionRoles` en el esquema del tenant,
        hacemos la consulta de forma segura y devolvemos None ante cualquier fallo.
        """
        try:
            from django.apps import apps
            UserRoles = apps.get_model('permission', 'UserRoles')
            ur = UserRoles.objects.filter(user=self).select_related('rol').order_by('-created').first()
            if ur:
                return ur.rol
        except Exception:
            # No romper si por alguna razón el modelo no está disponible desde este contexto
            return None
        return None

    # Este FK sí es a public (Client es shared en django-tenants)
    client = models.ForeignKey(CLIENT_FK, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Cliente')

    # 2FA (lo conservamos en el user por ahora; más adelante iremos a UserProfile si querés)
    otp_secret = models.CharField(max_length=32, blank=True, null=True)
    is_2fa_enabled = models.BooleanField(default=False)

    # Helpers existentes
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
        return bool(self.otp_secret)

    # Tenant-aware helpers
    @classmethod
    def for_client(cls, client):
        """Return a queryset of users belonging to the given client (public Client instance)."""
        if client is None:
            return cls.objects.none()
        return cls.objects.filter(client=client)

    @classmethod
    def for_current_tenant(cls):
        """Return users for the current tenant inferred from the DB connection.

        This uses django-tenants' `connection.tenant` (or `connection.schema_name`) to
        resolve the current client. If no tenant is available, returns an empty
        queryset to avoid leaking all users from PUBLIC.
        """
        try:
            from django.db import connection
            tenant = getattr(connection, "tenant", None)
            if tenant is None:
                # try schema_name (fallback)
                schema_name = getattr(connection, "schema_name", None)
                if not schema_name:
                    return cls.objects.none()
                # try to import Client lazily to avoid circular imports
                from client.models import Client
                tenant = Client.objects.filter(schema_name=schema_name).first()

            if tenant is None:
                return cls.objects.none()

            return cls.objects.filter(client=tenant)
        except Exception:
            return cls.objects.none()

class TenantMembership(models.Model):
    """Relaciona usuarios con tenants (clients) específicos."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    client = models.ForeignKey(CLIENT_FK, on_delete=models.CASCADE, related_name="memberships")  # si tu app es 'clients', cambialo
    is_active = models.BooleanField(default=True)
    # opcional: rol "macro" por tenant (los permisos granulares de Contrasena quedan igual en tu app actual)
    role = models.CharField(max_length=50, blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "client")]

    def __str__(self):
        return f"{self.user.username} @ {self.client.schema_name} ({'activo' if self.is_active else 'inactivo'})"


class TenantSettings(models.Model):
    client = models.OneToOneField(CLIENT_FK, on_delete=models.CASCADE, related_name="settings")
    # Migrados/compatibles con tu GlobalSettings (por ahora solo los creamos; migraremos luego)
    multifactor_status = models.PositiveSmallIntegerField(default=0)  # usaremos tus choices luego
    is_admin_dash_active = models.BooleanField(default=False)
    menu_color = models.CharField(max_length=7, blank=True, null=True, default="#212629")
    company_name = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    # Políticas SSO que vamos a usar en Fase 3/4
    sso_google_enabled = models.BooleanField(default=True)
    sso_autolink_by_email = models.BooleanField(default=True)
    sso_google_requires_2fa = models.BooleanField(default=False)

    def __str__(self):
        return f"Settings({self.client.schema_name})"
    




class AuthEvent(models.Model):
    LOGIN_PASSWORD = "login_password"
    LOGIN_GOOGLE = "login_google"
    SSO_CONSUME = "sso_consume"
    TWOFA_VERIFY = "twofa_verify"

    EVENT_CHOICES = [
        (LOGIN_PASSWORD, "Login (password)"),
        (LOGIN_GOOGLE, "Login (google)"),
        (SSO_CONSUME, "SSO consume"),
        (TWOFA_VERIFY, "2FA verify"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    # Nota: Client en PUBLIC (tu app compartida)
    client = models.ForeignKey(CLIENT_FK, null=True, blank=True, on_delete=models.SET_NULL)
    event = models.CharField(max_length=32, choices=EVENT_CHOICES)
    success = models.BooleanField(default=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    ua = models.TextField(null=True, blank=True)
    provider = models.CharField(max_length=20, blank=True, null=True)  # p.ej. "google"
    meta = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        who = self.user.email if self.user else "anon"
        cli = getattr(self.client, "schema_name", "—")
        return f"{self.event} [{ 'OK' if self.success else 'FAIL' }] {who} @ {cli}"
