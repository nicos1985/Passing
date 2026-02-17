from django.contrib import admin
from .models import InformationAssets

from .models import AssetAction

# Register your models here.

class InformationAssetAdmin(admin.ModelAdmin):
    list_display = ('id','name' , 'description', 'acquisition_date' ,'status', 'asset_type', 'owner')
    readonly_fields=('created', 'updated')
    search_fields = ('name',)    # Agregar filtro por fechas y otros campos
    list_filter = ('created', 'status', 'asset_type', 'owner')


admin.site.register(InformationAssets ,InformationAssetAdmin)


class AssetActionAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset', 'get_asset_name', 'action_type', 'user', 'performed_by', 'timestamp')
    readonly_fields = ('timestamp',)
    list_filter = ('action_type', 'timestamp')
    search_fields = ('asset__name', 'user__username')

    def get_asset_name(self, obj):
        return obj.asset.name
    get_asset_name.short_description = 'Activo'


admin.site.register(AssetAction, AssetActionAdmin)


