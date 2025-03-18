from django.contrib import admin
from .models import InformationAssets

# Register your models here.

class InformationAssetAdmin(admin.ModelAdmin):
    list_display = ('id','name' , 'description', 'acquisition_date' ,'status', 'category', 'owner')
    readonly_fields=('created', 'updated')
    search_fields = ('name',)    # Agregar filtro por fechas y otros campos
    list_filter = ('created', 'status', 'category', 'owner')


admin.site.register(InformationAssets ,InformationAssetAdmin)


