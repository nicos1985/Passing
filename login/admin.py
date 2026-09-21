from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin import AdminSite
from django.contrib.auth.forms import AuthenticationForm
from django.urls import path
from .forms import AdminLoginForm


# Register your models here.
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'is_superuser', 'is_staff', 'email', 'is_active')

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_module_permission = has_view_permission

    def has_delete_permission(self, request, obj=None):
        return False  # Deactivate via the application's protected workflow.


admin.site.register(CustomUser ,CustomUserAdmin)
