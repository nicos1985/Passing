from django.contrib import admin
from .models import ContraPermission, UserRoles
from .models import PermissionRoles
# Register your models here.

class ContraPermissionAdmin(admin.ModelAdmin):
    readonly_fields=('created', 'updated')
    list_display = ('user_id', 'contra_id', 'permission', 'created', 'updated')

class PermissionRolesAdmin(admin.ModelAdmin):
    readonly_fields=('created',)
    list_display = ('id','rol_name', 'comment','is_active', 'created')

class UserRolesAdmin(admin.ModelAdmin):
    readonly_fields=('created',)
    list_display = ('id','user', 'rol', 'created')


admin.site.register(ContraPermission ,ContraPermissionAdmin)
admin.site.register(PermissionRoles ,PermissionRolesAdmin)
admin.site.register(UserRoles ,UserRolesAdmin)
