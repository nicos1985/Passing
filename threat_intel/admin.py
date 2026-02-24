from django.contrib import admin
from .models import IntelThreatLink


@admin.register(IntelThreatLink)
class IntelThreatLinkAdmin(admin.ModelAdmin):
	"""Admin para gestionar las vinculaciones entre IntelItem y Threat."""
	list_display = ("intel_item", "resources_threat", "match_type", "confidence", "matched_at",)
	search_fields = ("intel_item__title", "resources_threat__name",)
	list_filter = ("match_type",)
