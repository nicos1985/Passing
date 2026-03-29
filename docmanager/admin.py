from django import forms
from django.contrib import admin

from .models import DocumentoControlado, IntegrationCredential


class IntegrationCredentialAdminForm(forms.ModelForm):
	secret_plain = forms.CharField(
		label="Secreto (JSON service account)",
		widget=forms.Textarea(attrs={"rows": 6}),
		required=False,
		help_text="Si se deja vacío, se conserva el valor actual.",
	)

	class Meta:
		model = IntegrationCredential
		fields = [
			"name",
			"service",
			"status",
			"key_id",
			"secret_plain",
			"created_by",
		]

	def save(self, commit=True):
		obj = super().save(commit=False)
		raw_secret = self.cleaned_data.get("secret_plain")
		if raw_secret:
			obj.set_secret(raw_secret)
		if commit:
			obj.save()
			self.save_m2m()
		return obj


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
	form = IntegrationCredentialAdminForm
	list_display = ("name", "service", "status", "key_id", "masked_secret", "updated_at")
	list_filter = ("service", "status")
	search_fields = ("name", "key_id")
	readonly_fields = ("created_at", "updated_at", "masked_secret")

	def masked_secret(self, obj):
		return obj.masked_secret()

	masked_secret.short_description = "Secreto"


@admin.register(DocumentoControlado)
class DocumentoControladoAdmin(admin.ModelAdmin):
	list_display = (
		"nombre_archivo",
		"drive_file_id",
		"estado_cumplimiento",
		"ultima_sincronizacion",
		"fecha_modificacion_drive",
		"frecuencia_revision_dias",
		"no_encontrado",
	)
	list_filter = ("no_encontrado", "credencial")
	search_fields = ("nombre_archivo", "drive_file_id")
	readonly_fields = ("ultima_sincronizacion", "fecha_modificacion_drive", "created_at", "updated_at")
	autocomplete_fields = ("credencial",)

