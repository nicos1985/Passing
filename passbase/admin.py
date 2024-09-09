from django.contrib import admin
from .models import Contrasena, LogData, SeccionContra



# Register your models here.

class ContrasenaAdmin(admin.ModelAdmin):
    list_display = ('id','nombre_contra' , 'seccion', 'info' ,'usuario')
    readonly_fields=('created', 'updated')

    # Agregar búsqueda por campos (nombre, usuario, etc.)
    search_fields = ('nombre_contra', 'usuario', 'seccion', 'hash' )
    
    # Agregar filtro por fechas y otros campos
    list_filter = ('created', 'seccion', 'usuario', 'hash')

class LogDataAdmin(admin.ModelAdmin):
    list_display = ('contraseña', 'entidad', 'usuario', 'action', 'created')
    readonly_fields=('created',)
    
class SeccionContAdmin(admin.ModelAdmin):
    list_display= ('nombre_seccion',)
    readonly_fields=('created', 'updated')

admin.site.register(SeccionContra ,SeccionContAdmin)
admin.site.register(Contrasena, ContrasenaAdmin)
admin.site.register(LogData ,LogDataAdmin)
