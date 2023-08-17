from django.contrib import admin
from .models import Contrasena, LogData, SeccionContra



# Register your models here.

class ContrasenaAdmin(admin.ModelAdmin):
    readonly_fields=('created', 'updated')

class LogDataAdmin(admin.ModelAdmin):
    readonly_fields=('created',)
    
class SeccionContAdmin(admin.ModelAdmin):
    readonly_fields=('created', 'updated')

admin.site.register(SeccionContra ,SeccionContAdmin)
admin.site.register(Contrasena, ContrasenaAdmin)
admin.site.register(LogData ,LogDataAdmin)
