from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.forms import AuthenticationForm
from django.urls import path
from .forms import AdminLoginForm


# Register your models here.
from .models import CustomUser

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'is_superuser', 'is_staff', 'email', 'is_active')


admin.site.register(CustomUser ,CustomUserAdmin)