from django.contrib import admin
from .models import TenantMembership, TenantSettings, CustomUser, AuthEvent

@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "client", "is_active", "role", "joined_at")
    list_filter = ("is_active", "client")
    search_fields = ("user__username", "user__email", "client__schema_name")

@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ("client", "company_name", "is_active", "sso_google_enabled", "sso_google_requires_2fa")
    list_filter = ("is_active", "sso_google_enabled", "sso_google_requires_2fa")
    search_fields = ("client__schema_name", "company_name")

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_active", "client", "is_2fa_enabled")
    search_fields = ("username", "email")
    list_filter = ("is_active", "is_2fa_enabled", "client")



@admin.register(AuthEvent)
class AuthEventAdmin(admin.ModelAdmin):
    list_display = ("event", "success", "user", "client", "provider", "at")
    list_filter = ("event", "success", "provider", "client")
    search_fields = ("user__email", "user__username", "client__schema_name")
