from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from passbase.crypto import decrypt_data, encrypt_data


class IntegrationCredential(models.Model):
	"""Credenciales de servicios externos (por ahora, Google Drive) cifradas con Fernet."""

	class Service(models.TextChoices):
		GOOGLE_DRIVE = "google_drive", "Google Drive"

	class Status(models.TextChoices):
		ACTIVE = "active", _("Activa")
		INACTIVE = "inactive", _("Inactiva")
		REVOKED = "revoked", _("Revocada")

	name = models.CharField(max_length=128, verbose_name=_("Nombre visible"))
	service = models.CharField(max_length=64, choices=Service.choices, default=Service.GOOGLE_DRIVE)
	status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
	key_id = models.CharField(max_length=128, blank=True, verbose_name=_("Identificador interno"))
	secret_encrypted = models.TextField(verbose_name=_("Secreto cifrado"))
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="integration_credentials",
		verbose_name=_("Creado por"),
	)
	created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Creado"))
	updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Actualizado"))

	class Meta:
		verbose_name = _("Credencial de integración")
		verbose_name_plural = _("Credenciales de integración")
		ordering = ("-updated_at", "-id")

	def __str__(self):
		return f"{self.get_service_display()} :: {self.name}"

	@property
	def is_active(self) -> bool:
		return self.status == self.Status.ACTIVE

	def set_secret(self, raw_secret: str) -> None:
		"""Cifra y guarda el secreto en `secret_encrypted`."""
		if not raw_secret:
			raise ValidationError("El secreto no puede estar vacío.")
		self.secret_encrypted = encrypt_data(raw_secret)

	def get_secret(self) -> str | None:
		"""Devuelve el secreto descifrado o None si no hay valor."""
		if not self.secret_encrypted:
			return None
		return decrypt_data(self.secret_encrypted)

	def masked_secret(self) -> str:
		"""Devuelve una versión enmascarada para mostrar en admin/listados."""
		if not self.secret_encrypted:
			return ""
		# No se descifra para evitar exponer valores; solo indicamos longitud aproximada.
		return f"*** ({len(self.secret_encrypted)} chars cifrados)"


class DocumentoControlado(models.Model):
	"""Documento controlado en Drive con regla de vigencia y seguimiento."""

	drive_file_id = models.CharField(max_length=255, unique=True, verbose_name=_("ID de Drive"))
	carpeta_drive_id = models.CharField(max_length=255, blank=True, verbose_name=_("Carpeta Drive"))
	credencial = models.ForeignKey(
		IntegrationCredential,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="documentos",
		verbose_name=_("Credencial de servicio"),
	)
	nombre_archivo = models.CharField(max_length=255, verbose_name=_("Nombre en Drive"))
	link_edicion = models.URLField(verbose_name=_("Link de edición"))
	ultima_sincronizacion = models.DateTimeField(null=True, blank=True, verbose_name=_("Última sincronización"))
	fecha_modificacion_drive = models.DateTimeField(null=True, blank=True, verbose_name=_("Modificado en Drive"))
	ultimo_editor_drive = models.CharField(max_length=255, blank=True, verbose_name=_("Último editor"))
	frecuencia_revision_dias = models.PositiveIntegerField(default=90, verbose_name=_("Frecuencia de revisión (días)"))
	no_encontrado = models.BooleanField(default=False, verbose_name=_("No encontrado en Drive"))
	created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Creado"))
	updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Actualizado"))

	class Meta:
		verbose_name = _("Documento controlado")
		verbose_name_plural = _("Documentos controlados")
		ordering = ("-fecha_modificacion_drive", "-updated_at")

	def __str__(self):
		return f"{self.nombre_archivo} ({self.drive_file_id})"

	@property
	def dias_restantes(self) -> int | None:
		if not self.fecha_modificacion_drive:
			return None
		limite = self.fecha_modificacion_drive + timedelta(days=self.frecuencia_revision_dias)
		delta = limite - timezone.now()
		return delta.days

	@property
	def estado_cumplimiento(self) -> str:
		"""Semáforo simple: verde=al día, amarillo=próximo, rojo=vencido."""
		if self.no_encontrado:
			return "no_encontrado"
		if not self.fecha_modificacion_drive:
			return "sin_datos"

		limite = self.fecha_modificacion_drive + timedelta(days=self.frecuencia_revision_dias)
		now = timezone.now()
		remaining = (limite - now).total_seconds()

		if remaining <= 0:
			return "vencido"

		# Amarillo cuando falta <= 20% del período o <= 7 días (lo que ocurra primero)
		threshold_seconds = min(self.frecuencia_revision_dias * 0.2 * 86400, 7 * 86400)
		if remaining <= threshold_seconds:
			return "proximo"
		return "al_dia"

	@property
	def semaforo_color(self) -> str:
		mapping = {
			"al_dia": "#18a558",    # verde
			"proximo": "#f6c344",   # amarillo
			"vencido": "#e34f4f",   # rojo
			"no_encontrado": "#6b7280",  # gris
			"sin_datos": "#9ca3af",      # gris claro
		}
		return mapping.get(self.estado_cumplimiento, "#9ca3af")

	def apply_drive_metadata(self, metadata: dict) -> None:
		"""Actualiza campos locales a partir de metadata de la API Drive."""
		if not metadata:
			return

		nombre = metadata.get("name")
		web_view_link = metadata.get("webViewLink") or metadata.get("alternateLink")
		modified_time = metadata.get("modifiedTime")
		editor = None
		last_user = metadata.get("lastModifyingUser")
		if last_user:
			editor = last_user.get("displayName") or last_user.get("emailAddress")

		self.nombre_archivo = nombre or self.nombre_archivo
		if web_view_link:
			self.link_edicion = web_view_link

		if modified_time:
			parsed = parse_datetime(modified_time)
			if parsed and timezone.is_naive(parsed):
				parsed = timezone.make_aware(parsed)
			self.fecha_modificacion_drive = parsed

		if editor:
			self.ultimo_editor_drive = editor

		self.no_encontrado = False
		self.ultima_sincronizacion = timezone.now()

