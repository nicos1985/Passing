from django.contrib import admin
from .models import ContraPermission, UserRoles
from .models import PermissionRoles
from passbase.models import Contrasena
# Register your models here.

class ContraPermissionAdmin(admin.ModelAdmin):
    readonly_fields=('created', 'updated')
    list_display = ('user_id', 'contra_id', 'permission', 'created', 'updated')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(contra_id__is_personal=False)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'contra_id':
            kwargs['queryset'] = Contrasena.objects.filter(is_personal=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PermissionRolesAdmin(admin.ModelAdmin):
    readonly_fields=('created',)
    list_display = ('id','rol_name', 'comment','is_active', 'created')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'contrasenas':
            kwargs['queryset'] = Contrasena.objects.filter(is_personal=False)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

class UserRolesAdmin(admin.ModelAdmin):
    readonly_fields=('created',)
    list_display = ('id','user', 'rol', 'created')


admin.site.register(ContraPermission ,ContraPermissionAdmin)
admin.site.register(PermissionRoles ,PermissionRolesAdmin)
admin.site.register(UserRoles ,UserRolesAdmin)
