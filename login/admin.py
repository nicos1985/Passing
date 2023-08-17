from django.contrib import admin

# Register your models here.
from .models import CustomUser

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'is_superuser', 'is_staff', 'email', 'is_active')


admin.site.register(CustomUser ,CustomUserAdmin)