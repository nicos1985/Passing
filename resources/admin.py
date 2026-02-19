from django.contrib import admin
from django.shortcuts import render
from django.urls import path, reverse
from .models import InformationAssets
from .models import AssetAction

from .models import (
    ChecklistTemplate,
    ChecklistItem,
    VendorChecklist,
    VendorEvaluation,
    VendorEvaluationItem,
)
from .models import Vendor
from .views import (
    build_pending_evaluations_context,
    get_pending_evaluations_queryset,
)

# Register your models here.

class InformationAssetAdmin(admin.ModelAdmin):
    list_display = ('id','name' , 'description', 'acquisition_date' ,'status', 'asset_type', 'owner')
    readonly_fields=('created', 'updated')
    search_fields = ('name', 'owner__username')    # Agregar filtro por fechas y otros campos
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


# --- Admin para Checklists y Evaluaciones de Proveedores ---
class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1


class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'active', 'created')
    search_fields = ('name', 'description')
    inlines = (ChecklistItemInline,)


class VendorChecklistAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'template', 'customized')
    search_fields = ('vendor__name', 'template__name')


class VendorChecklistInline(admin.TabularInline):
    model = VendorChecklist
    extra = 0


class VendorEvaluationInline(admin.TabularInline):
    model = VendorEvaluation
    extra = 0
    readonly_fields = ('scheduled_date', 'status', 'performed_by')


class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'vendor_type', 'status')
    search_fields = ('name', 'owner__username')
    inlines = (VendorChecklistInline, VendorEvaluationInline)


admin.site.register(Vendor, VendorAdmin)


class VendorEvaluationItemInline(admin.TabularInline):
    model = VendorEvaluationItem
    extra = 0
    readonly_fields = ('question_text',)


class VendorEvaluationAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'scheduled_date', 'status', 'performed_by', 'performed_at')
    list_filter = ('status', 'scheduled_date')
    search_fields = ('vendor__name', 'notes')
    inlines = (VendorEvaluationItemInline,)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'pending-evaluations/',
                self.admin_site.admin_view(self.pending_evaluations_view),
                name='resources_vendorevaluation_pending',
            ),
        ]
        return custom_urls + urls

    def pending_evaluations_view(self, request):
        include_all = request.user.is_staff or request.user.is_superuser
        queryset = get_pending_evaluations_queryset(request.user, include_all=include_all)
        context = build_pending_evaluations_context(request, queryset)
        context.update({
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Evaluaciones pendientes',
            'change_list_url': reverse('admin:resources_vendorevaluation_changelist'),
        })
        return render(request, 'vendor_evaluation_pending_list.html', context)


class VendorEvaluationItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'evaluation', 'question_text', 'result')
    list_filter = ('result',)
    search_fields = ('question_text', 'observations')


admin.site.register(ChecklistTemplate, ChecklistTemplateAdmin)
admin.site.register(VendorChecklist, VendorChecklistAdmin)
admin.site.register(VendorEvaluation, VendorEvaluationAdmin)
admin.site.register(VendorEvaluationItem, VendorEvaluationItemAdmin)


