from django.contrib import admin
from .models import ContraPermission
# Register your models here.

class ContraPermissionAdmin(admin.ModelAdmin):
    readonly_fields=('created', 'updated')
    list_display = ('user_id', 'contra_id', 'permission', 'created', 'updated')



admin.site.register(ContraPermission ,ContraPermissionAdmin)

