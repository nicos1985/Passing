from django.db import models
# accounts/models.py (PUBLIC)
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.db import connection
from django.utils.translation import gettext_lazy as _


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
    """Usuario personalizado del hub con campos adicionales y helpers tenant-aware."""
    avatar = models.ImageField(blank=True, null=True, upload_to=avatar_upload_to, verbose_name=_('Avatar'))
    position = models.CharField(max_length=80, null=True, verbose_name=_('Puesto'))
    email = models.EmailField(unique=True, verbose_name=_('Correo Electrónico'))
    documento = models.CharField(max_length=8, blank=True, null=True, verbose_name=_('Documento'))
    birth_date = models.DateField(blank=True, null=True, verbose_name=_('Fecha Nacimiento'))
    address = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Domicilio'))
    tel_number = models.CharField(max_length=13, blank=True, null=True, verbose_name=_('Nro Telefono'))
    admission_date = models.DateField(blank=True, null=True, verbose_name=_('Fecha Ingreso'))
    departure_date = models.DateField(blank=True, null=True, verbose_name=_('Fecha Egreso'))
    departure_motive = models.CharField(max_length=1000, blank=True, null=True, verbose_name=_('Motivo de baja'))
    menu_color = models.CharField(max_length=7, null=True, blank=True, verbose_name=_('Color de menu'), default='#212629')

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
    client = models.ForeignKey(CLIENT_FK, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Cliente'))

    # 2FA (lo conservamos en el user por ahora; más adelante iremos a UserProfile si querés)
    otp_secret = models.CharField(max_length=32, blank=True, null=True, verbose_name=_('Secreto OTP'))
    is_2fa_enabled = models.BooleanField(default=False, verbose_name=_('2FA Habilitado'))
    # Preferencia de idioma para la interfaz de usuario (UI) - guarda código de idioma, p.ej. 'es' o 'en'
    language = models.CharField(max_length=10, blank=True, null=True, default='es', verbose_name=_('Idioma'))

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

    def get_preferred_language(self):
        """Devuelve el lenguaje preferido del usuario o `None` si no está configurado."""
        return self.language or None

    # Tenant-aware helpers
    @classmethod
    def for_client(cls, client):
        """Devuelve usuarios activos asociados al cliente público especificado."""
        if client is None:
            return cls.objects.none()
        return cls.objects.filter(client=client)

    @classmethod
    def for_current_tenant(cls):
        """Restringe el queryset al tenant activo considerando la conexión actual."""
        try:
            from django.db import connection
            tenant = getattr(connection, "tenant", None)
            # fallback: try to resolve client from connection.schema_name
            if tenant is None:
                schema_name = getattr(connection, "schema_name", None)
                if schema_name:
                    from client.models import Client
                    tenant = Client.objects.filter(schema_name=schema_name).first()

            if not tenant:
                return cls.objects.none()

            return cls.objects.filter(client=tenant)
        except Exception:
            return cls.objects.none()

class TenantMembership(models.Model):
    """Relaciona usuarios con tenants (clients) específicos."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships", verbose_name=_('Usuario'))
    client = models.ForeignKey(CLIENT_FK, on_delete=models.CASCADE, related_name="memberships", verbose_name=_('Cliente'))  # si tu app es 'clients', cambialo
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))
    # opcional: rol "macro" por tenant (los permisos granulares de Contrasena quedan igual en tu app actual)
    role = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('Rol'))
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Fecha de ingreso'))

    class Meta:
        unique_together = [("user", "client")]

    def __str__(self):
        return f"{self.user.username} @ {self.client.schema_name} ({'activo' if self.is_active else 'inactivo'})"


class TenantSettings(models.Model):
    """Configuraciones por cliente que controlan SSO, recordatorios y presencia del dash."""
    client = models.OneToOneField(CLIENT_FK, on_delete=models.CASCADE, related_name="settings", verbose_name=_('Cliente'))
    # Migrados/compatibles con tu GlobalSettings (por ahora solo los creamos; migraremos luego)
    multifactor_status = models.PositiveSmallIntegerField(default=0, verbose_name=_('Estado del segundo factor'))  # usaremos tus choices luego
    is_admin_dash_active = models.BooleanField(default=False, verbose_name=_('Dashboard administrador activo'))
    menu_color = models.CharField(max_length=7, blank=True, null=True, default="#212629", verbose_name=_('Color del menú'))
    company_name = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('Nombre de la empresa'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))
    evaluation_reminder_days = models.PositiveSmallIntegerField(
        default=14,
        verbose_name=_('Días de aviso para evaluaciones'),
        help_text=_('Cuántos días antes del vencimiento se notifica a los owners.'),
    )
    created_at = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))
    updated_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Actualizado'))

    # Políticas SSO que vamos a usar en Fase 3/4
    sso_google_enabled = models.BooleanField(default=True, verbose_name=_('SSO Google habilitado'))
    sso_autolink_by_email = models.BooleanField(default=True, verbose_name=_('Autolink por email'))
    sso_google_requires_2fa = models.BooleanField(default=False, verbose_name=_('SSO Google requiere 2FA'))

    def __str__(self):
        return f"Settings({self.client.schema_name})"

    @property
    def reminder_lead_days(self):
        return max(0, self.evaluation_reminder_days or 0)

    @classmethod
    def for_client(cls, client):
        if client is None:
            return None
        return cls.objects.filter(client=client).first()
    




class AuthEvent(models.Model):
    """Registra eventos autenticación/SSO para auditoría y troubleshooting."""
    LOGIN_PASSWORD = _("login_password")
    LOGIN_GOOGLE = _("login_google")
    SSO_CONSUME = _("sso_consume")
    TWOFA_VERIFY = _("twofa_verify")

    EVENT_CHOICES = [
        (LOGIN_PASSWORD, _("Login (password)")),
        (LOGIN_GOOGLE, _("Login (google)")),
        (SSO_CONSUME, _("SSO consume")),
        (TWOFA_VERIFY, _("2FA verify")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Usuario'))
    # Nota: Client en PUBLIC (tu app compartida)
    client = models.ForeignKey(CLIENT_FK, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Cliente'))
    event = models.CharField(max_length=32, choices=EVENT_CHOICES, verbose_name=_('Evento'))
    success = models.BooleanField(default=True, verbose_name=_('Éxito'))
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('IP'))
    ua = models.TextField(null=True, blank=True, verbose_name=_('User Agent'))
    provider = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Proveedor'))  # p.ej. "google"
    meta = models.JSONField(default=dict, blank=True, verbose_name=_('Metadatos'))
    at = models.DateTimeField(default=timezone.now, verbose_name=_('Fecha y hora'))

    def __str__(self):
        who = self.user.email if self.user else "anon"
        cli = getattr(self.client, "schema_name", "—")
        return f"{self.event} [{ 'OK' if self.success else 'FAIL' }] {who} @ {cli}"
