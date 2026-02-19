from django.contrib import admin
from .models import TenantMembership, TenantSettings, CustomUser, AuthEvent

@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    """Admin para revisar roles y estado de membresía de usuarios por tenant."""

    list_display = ("user", "client", "is_active", "role", "joined_at")
    list_filter = ("is_active", "client")
    search_fields = ("user__username", "user__email", "client__schema_name")

@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """Expone las configuraciones de SSO y recordatorios por cliente."""

    list_display = (
        "client",
        "company_name",
        "is_active",
        "sso_google_enabled",
        "sso_google_requires_2fa",
        "evaluation_reminder_days",
    )
    list_filter = ("is_active", "sso_google_enabled", "sso_google_requires_2fa")
    search_fields = ("client__schema_name", "company_name")

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """Admin básico para gestionar usuarios hub y su estado de 2FA."""

    list_display = ("username", "email", "is_active", "client", "is_2fa_enabled")
    search_fields = ("username", "email")
    list_filter = ("is_active", "is_2fa_enabled", "client")



@admin.register(AuthEvent)
class AuthEventAdmin(admin.ModelAdmin):
    """Tabla con eventos de login/SSO para auditar intentos y errores."""

    list_display = ("event", "success", "user", "client", "provider", "at")
    list_filter = ("event", "success", "provider", "client")
    search_fields = ("user__email", "user__username", "client__schema_name")
