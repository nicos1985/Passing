from django.contrib import admin

from .models import CheckResult, Delivery, DeploymentMarker, HourlySummary, Incident, MaintenanceWindow, Monitor, MonitorGroup


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "host", "state", "enabled", "last_checked_at")
    search_fields = ("name", "host")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("monitor", "started_at", "recovered_at", "bitrix_deal_id")
    readonly_fields = ("started_at", "recovered_at", "bitrix_deal_id")


admin.site.register(CheckResult)
admin.site.register(HourlySummary)
admin.site.register(Delivery)
admin.site.register(MaintenanceWindow)
admin.site.register(DeploymentMarker)

admin.site.register(MonitorGroup)
