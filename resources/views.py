from warnings import filters
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, JsonResponse
from .models import (
    InformationAssets,
    RiskEvaluation,
    Threat,
    Treatment,
    Vendor,
    Project,
    ClientCompany,
    Vulnerability,
    ChecklistTemplate,
    VendorEvaluation,
    VendorEvaluationStatus,
    TreatmentStage,
    TypeTreatment,
    Controls,
    TreatmentOportunity,
    ApplicationPeriodicity,
    ControlAutomation,
    Priority,
)
from .forms import InformationAssetsForm, ProjectAssetsForm, RiskEvaluationForm, ThreatForm, TreatmentForm, VendorForm, ClientAssetsForm, VulnerabilityForm
from .forms import LoanForm, ReturnForm
from .forms import ChecklistTemplateForm, ChecklistItemForm, VendorChecklistForm, VendorEvaluationForm, VendorEvaluationItemFormSet
from django.utils.text import capfirst
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Q, Count
import logging
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from login.models import CustomUser
from accounts.models import TenantSettings
from .models import AssetAction, AssetActionType
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.forms import inlineformset_factory
from .models import ChecklistTemplate, ChecklistItem, VendorChecklist
from .forms import ChecklistTemplateForm, ChecklistItemForm, VendorChecklistForm

# Optional imports to support mapping from threat_intel -> resources
try:
    from threat_intel.models import IntelThreatLink, IntelItem
except Exception:
    IntelThreatLink = None
    IntelItem = None


# Create your views here.

logger = logging.getLogger(__name__)
################################### Asset Views ###########################

class DynamicModelListView(ListView):
    """Lista cualquier modelo con filtros e información dinámica basada en su meta."""
    template_name = 'list_resource.html'
    EXCLUDED_FIELDS = ['created', 'updated', 'id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.model
        fields = model._meta.fields

        # Campos mostrados
        context['fields'] = [
            {'name': field.name, 'verbose': field.verbose_name.title()}
            for field in fields if field.name not in self.EXCLUDED_FIELDS
        ]

        # Filtros: choices, booleanos, foreign keys
        filters = {}

        for field in fields:
            if field.name in self.EXCLUDED_FIELDS:
                continue

            # Campos con choices
            if field.choices:
                filters[field.name] = [{'value': c[1], 'label': c[1]} for c in field.choices]

            # BooleanField
            elif isinstance(field, models.BooleanField):
                filters[field.name] = [
                    {'value': 'True', 'label': 'Sí'},
                    {'value': 'False', 'label': 'No'},
                ]

            # ForeignKey
            elif isinstance(field, models.ForeignKey):
                related = field.related_model.objects.all()
                filters[field.name] = [{'value': str(obj.pk), 'label': str(obj)} for obj in related]
            
            # si es datetime o date, solo marcamos el tipo
            elif isinstance(field, models.DateField) or isinstance(field, models.DateTimeField):
                filters[field.name] = {'type': 'date'}  # Sólo marcamos que es tipo fecha

        context['dynamic_filters'] = filters
        context['verbose_name_plural'] = model._meta.verbose_name_plural.title()
        # Expose model_name for templates (avoid accessing _meta from templates)
        context['model_name'] = model._meta.model_name
        return context

    

class AssetListView(LoginRequiredMixin, DynamicModelListView):
    """Expone los activos de información junto con indicadores de acciones pendientes."""
    model = InformationAssets
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        # Attach pending actions count to each asset in the list for UI badges
        assets = context.get('object_list') or self.get_queryset()
        asset_ids = [a.pk for a in assets]
        pending_map = {}
        if asset_ids:
            qs = AssetAction.objects.filter(asset_id__in=asset_ids, status='PENDING').values('asset_id').annotate(count=Count('pk'))
            pending_map = {item['asset_id']: item['count'] for item in qs}

        # Set attribute on asset objects for template convenience
        for a in assets:
            try:
                a.pending_actions_count = pending_map.get(a.pk, 0)
            except Exception:
                a.pending_actions_count = 0

        context['pending_map'] = pending_map
        return context


class AssetCreateView(LoginRequiredMixin, CreateView):
    """Permite crear activos de información conservando enlaces relacionados."""
    model = InformationAssets
    form_class = InformationAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('informationassets-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        # related links for quick navigation
        try:
            context['related_links'] = [
                (reverse(context['list_url_name']), f'Ver {context["verbose_name_plural"]}')
            ]
        except Exception:
            context['related_links'] = []
        return context

class AssetUpdateView(LoginRequiredMixin, UpdateView):
    """Gestiona la edición de activos de información con contexto enriquecido."""
    model = InformationAssets
    form_class = InformationAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('informationassets-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        try:
            context['related_links'] = [
                (reverse(context['list_url_name']), f'Ver {context["verbose_name_plural"]}')
            ]
        except Exception:
            context['related_links'] = []
        return context

class AssetDetailView(LoginRequiredMixin, DetailView):
    """Muestra el detalle completo de un activo de información."""
    model=InformationAssets
    template_name = 'detail-resource.html'
    login_url = 'login'


class LoanCreateView(LoginRequiredMixin, CreateView):
    """Solicita un préstamo de activo y envía el correo de confirmación al destinatario."""
    model = AssetAction
    form_class = LoanForm
    template_name = 'CU-asset-action.html'
    login_url = 'login'

    def get_success_url(self):
        return reverse_lazy('informationassets-list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.performed_by = self.request.user
        obj.action_type = AssetActionType.LOAN
        # Keep in pending until beneficiary confirms
        obj.status = AssetAction.AssetActionStatus.PENDING
        obj.save()

        # send confirmation email to beneficiary
        try:
            token = str(obj.confirmation_token)
            confirm_url = self.request.build_absolute_uri(reverse('asset-action-confirm', args=[token]))
            subject = f"Confirmación de préstamo: {obj.asset.name}"
            body = f"Se ha solicitado un préstamo del activo '{obj.asset.name}'.\n\nDescripción: {obj.description or '-'}\nFecha estimada de devolución: {obj.due_date or '-'}\nSolicitado por: {obj.performed_by.get_full_name() or obj.performed_by.username}\n\nPara confirmar el préstamo haga click en el siguiente enlace:\n{confirm_url}\n\nSi no reconoce esta solicitud, ignore este correo."
            if obj.user and obj.user.email:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [obj.user.email])
        except Exception:
            logger.exception('Error enviando email de confirmación de préstamo')

        messages.info(self.request, 'Préstamo creado como pendiente. Se ha enviado una solicitud de confirmación al usuario destino.')
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        asset_id = self.request.GET.get('asset')
        if asset_id:
            initial['asset'] = asset_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_label'] = 'Préstamo'
        ctx['action_icon'] = 'fa-hand-holding'
        # if asset provided, expose asset for template
        asset_id = self.request.GET.get('asset') or self.request.POST.get('asset')
        if asset_id:
            try:
                ctx['asset_obj'] = InformationAssets.objects.get(pk=asset_id)
            except Exception:
                ctx['asset_obj'] = None
        # related links: asset detail and asset list
        try:
            links = []
            links.append((reverse('informationassets-list'), 'Ver activos'))
            if ctx.get('asset_obj'):
                links.append((reverse('informationassets-detail', args=[ctx['asset_obj'].pk]), 'Ver activo'))
            ctx['related_links'] = links
        except Exception:
            ctx['related_links'] = []
        return ctx


class ReturnCreateView(LoginRequiredMixin, CreateView):
    """Solicita la devolución de un activo y notifica al encargado actual."""
    model = AssetAction
    form_class = ReturnForm
    template_name = 'CU-asset-action.html'
    login_url = 'login'

    def get_success_url(self):
        return reverse_lazy('informationassets-list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.performed_by = self.request.user
        obj.action_type = AssetActionType.RETURN
        obj.status = AssetAction.AssetActionStatus.PENDING
        obj.save()

        # send confirmation email to the recipient (current holder)
        try:
            token = str(obj.confirmation_token)
            confirm_url = self.request.build_absolute_uri(reverse('asset-action-confirm', args=[token]))
            subject = f"Confirmación de devolución: {obj.asset.name}"
            body = f"Se ha solicitado la devolución del activo '{obj.asset.name}'.\n\nDescripción: {obj.description or '-'}\nSolicitado por: {obj.performed_by.get_full_name() or obj.performed_by.username}\n\nPara confirmar la devolución haga click en el siguiente enlace:\n{confirm_url}\n\nSi no reconoce esta solicitud, ignore este correo."
            # send to the user who currently holds the asset
            recipient = None
            try:
                holder = obj.asset.get_current_holder()
                if holder and holder.email:
                    recipient = holder.email
            except Exception:
                recipient = None

            if recipient:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
        except Exception:
            logger.exception('Error enviando email de confirmación de devolución')

        messages.info(self.request, 'Devolución creada como pendiente. Se ha enviado una solicitud de confirmación al usuario actual que tiene el activo.')
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        asset_id = self.request.GET.get('asset')
        if asset_id:
            initial['asset'] = asset_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_label'] = 'Devolución'
        ctx['action_icon'] = 'fa-rotate-left'
        asset_id = self.request.GET.get('asset') or self.request.POST.get('asset')
        if asset_id:
            try:
                ctx['asset_obj'] = InformationAssets.objects.get(pk=asset_id)
            except Exception:
                ctx['asset_obj'] = None
        try:
            links = [(reverse('informationassets-list'), 'Ver activos')]
            if ctx.get('asset_obj'):
                links.append((reverse('informationassets-detail', args=[ctx['asset_obj'].pk]), 'Ver activo'))
            ctx['related_links'] = links
        except Exception:
            ctx['related_links'] = []
        return ctx


class AssetActionListView(LoginRequiredMixin, ListView):
    """Lista las acciones realizadas sobre un activo específico."""
    model = AssetAction
    template_name = 'asset-actions-list.html'
    context_object_name = 'actions'
    login_url = 'login'

    def get_queryset(self):
        asset_id = self.kwargs.get('asset_id')
        return AssetAction.objects.filter(asset_id=asset_id).order_by('-timestamp')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        asset_id = self.kwargs.get('asset_id')
        try:
            ctx['asset'] = InformationAssets.objects.get(pk=asset_id)
        except Exception:
            ctx['asset'] = None
        # Build enriched action items for template (include icon, overdue flag, asset name, due_date)
        actions = ctx.get('actions', [])
        items = []
        today = timezone.now().date()
        for act in actions:
            try:
                asset_obj = act.asset
            except Exception:
                asset_obj = None

            is_overdue = False
            if act.action_type == AssetActionType.LOAN and getattr(act, 'due_date', None) and asset_obj and asset_obj.is_loaned and today > act.due_date:
                is_overdue = True

            if act.action_type == AssetActionType.LOAN:
                icon = 'fa-hand-holding'
                icon_color = 'color: #198754 !important;'  # green
            else:
                icon = 'fa-rotate-left'
                icon_color = 'color: #0d6efd !important;'  # blue

            items.append({
                'act': act,
                'asset': asset_obj,
                'asset_name': asset_obj.name if asset_obj else '—',
                'due_date': act.due_date,
                'is_overdue': is_overdue,
                'icon': icon,
                'icon_color': icon_color,
            })

        ctx['action_items'] = items
        return ctx


class AssetActionAllListView(LoginRequiredMixin, ListView):
    """Muestra el historial global de acciones sobre activos, con filtro opcional por usuario."""
    model = AssetAction
    template_name = 'asset-actions-list.html'
    context_object_name = 'actions'
    login_url = 'login'

    def get_queryset(self):
        # Allow filtering by user via URL kwarg (asset-actions/user/<id>/)
        user_id = self.kwargs.get('user_id')
        qs = AssetAction.objects.all().order_by('-timestamp')
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['asset'] = None
        ctx['title'] = 'Historial de todos los activos'
        # If filtering by user, attach the user object to context for header
        user_id = self.kwargs.get('user_id')
        if user_id:
            try:
                ctx['filter_user'] = CustomUser.objects.get(pk=user_id)
                ctx['title'] = f"Historial de {ctx['filter_user'].get_full_name() or ctx['filter_user'].username}"
            except Exception:
                ctx['filter_user'] = None
        # Build enriched action items for template
        actions = ctx.get('actions', [])
        items = []
        today = timezone.now().date()
        for act in actions:
            try:
                asset_obj = act.asset
            except Exception:
                asset_obj = None

            is_overdue = False
            if act.action_type == AssetActionType.LOAN and getattr(act, 'due_date', None) and asset_obj and asset_obj.is_loaned and today > act.due_date:
                is_overdue = True

            icon = 'fa-hand-holding' if act.action_type == AssetActionType.LOAN else 'fa-rotate-left'

            icon_color = 'color: #198754 !important;' if act.action_type == AssetActionType.LOAN else 'color: #0d6efd !important;'

            items.append({
                'act': act,
                'asset': asset_obj,
                'asset_name': asset_obj.name if asset_obj else '—',
                'due_date': act.due_date,
                'is_overdue': is_overdue,
                'icon': icon,
                'icon_color': icon_color,
            })

        ctx['action_items'] = items
        return ctx


@login_required
def asset_tracking(request):
    """Lista de activos con su titular actual y el historial reciente."""
    assets = InformationAssets.objects.all()
    data = []
    for a in assets:
        holder = a.get_current_holder()
        recent_actions = a.actions.all()[:10]
        data.append({'asset': a, 'holder': holder, 'recent_actions': recent_actions})
    return render(request, 'asset-tracking.html', {'data': data})


@login_required
def confirm_asset_action(request, token):
    """Confirma la acción de un activo mediante token y actualiza su estado."""
    try:
        aa = AssetAction.objects.get(confirmation_token=token)
    except AssetAction.DoesNotExist:
        return HttpResponse('Token inválido o acción no encontrada.', status=404)

    if aa.status != AssetAction.AssetActionStatus.PENDING:
        return HttpResponse('Esta acción ya fue procesada.', status=400)

    # mark confirmed and save
    aa.status = AssetAction.AssetActionStatus.CONFIRMED
    aa.timestamp = timezone.now()
    try:
        aa.save()
    except ValidationError as e:
        # If the action cannot be confirmed due to business validation (e.g., trying to return without loan),
        # mark it as rejected and return a 400 with the error message.
        aa.status = AssetAction.AssetActionStatus.REJECTED
        aa.save(update_fields=['status'])
        return HttpResponse(f'No se pudo confirmar la acción: {e.messages}', status=400)

    # Simple response page
    return HttpResponse('Acción confirmada correctamente. Puede cerrar esta ventana.')

class GenericResourceDetailView(DetailView):
    """Detalle genérico basado en el modelo indicado, incluyendo campos y acciones auxiliares."""
    template_name = 'detail-resource.html'
    model = None  # importante: por compatibilidad, aunque se setea dinámicamente

    @classmethod
    def as_view(cls, **initkwargs):
        if 'model' not in initkwargs:
            raise ValueError("Debes pasar el modelo con 'model=...' al usar GenericResourceDetailView")
        return super().as_view(**initkwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        meta = obj.__class__._meta

        context['verbose_model_name'] = meta.verbose_name.title()
        context['model_name'] = meta.model_name  # For template use

        # Campos visibles (excluyendo ID, campos sensibles o FK pesados si querés)
        visible_fields = []
        for field in meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id', 'password']:
                if field.choices:
                    display_method = f"get_{field.name}_display"
                    value = getattr(obj, display_method)()
                else:
                    value = getattr(obj, field.name, None)

                visible_fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['fields'] = visible_fields
        # URLs auxiliares
        model_name = meta.model_name
        # Provide stage choices for templates when object is a Treatment
        try:
            if model_name == 'treatment':
                stage_field = meta.get_field('stage')
                context['stage_choices'] = list(stage_field.choices)
        except Exception:
            context['stage_choices'] = []
        try:
            context['edit_url'] = reverse(f'{model_name}-update', args=[obj.pk])
            context['delete_url'] = reverse(f'{model_name}-delete', args=[obj.pk])
            context['back_url'] = reverse(f'{model_name}-list')
        except:
            context['edit_url'] = None
            context['delete_url'] = None
            context['back_url'] = '#'

        # If the object is a Vendor, include its evaluations for direct access in the detail view
        try:
            if model_name == 'vendor':
                context['evaluations'] = getattr(obj, 'evaluations').all().order_by('-scheduled_date')
                context['create_evaluation_url'] = reverse('vendor-evaluation-create') + f'?vendor={obj.pk}'
        except Exception:
            context['evaluations'] = []
            context['create_evaluation_url'] = reverse('vendor-evaluation-create')

        return context



class AssetDeleteView(LoginRequiredMixin, DeleteView):
    """Borra un activo de información mostrando un resumen antes de confirmar."""
    model = InformationAssets
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('informationassets-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'informationassets-list'
        return context

####################################### Vendor Views ###########################

class VendorListView(LoginRequiredMixin, DynamicModelListView):
    """Lista proveedores con las mismas herramientas dinámicas que para otros recursos."""
    model = Vendor
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context


class VendorCreateView(LoginRequiredMixin, CreateView):
    """Permite registrar proveedores y vincular plantillas de checklist iniciales."""
    model = Vendor
    form_class = VendorForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('vendor-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        return context
    
    def form_valid(self, form):
        # Derive non-editable fields before persisting
        vendor = form.instance
        vendor.criticality = vendor.compute_criticality()
        vendor.control_period = vendor.compute_control_period()
        response = super().form_valid(form)
        try:
            template = form.cleaned_data.get('initial_checklist_template')
            if template and self.object:
                # create assignment if not exists
                VendorChecklist.objects.get_or_create(vendor=self.object, template=template, defaults={'customized': False})
        except Exception:
            pass
        scheduled = self.object.schedule_next_evaluation(from_date=self.object.start_date)
        if scheduled:
            messages.info(self.request, f'Primera evaluación pendiente programada para {scheduled.scheduled_date}')
        return response

class VendorUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza los datos de un proveedor conservando enlaces contextuales siempre."""
    model = Vendor
    form_class = VendorForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('vendor-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context

class VendorDetailView(LoginRequiredMixin, DetailView):
    """Presenta los detalles de un proveedor junto a sus métricas recientes."""
    model=Vendor
    template_name = 'detail-vendor.html'
    login_url = 'login'

class VendorDeleteView(LoginRequiredMixin, DeleteView):
    """Confirma la eliminación de un proveedor y redirige al listado."""
    model = Vendor
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('vendor-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'vendor-list'
        return context
    

############################# Project Views ###########################

class ProjectListView(LoginRequiredMixin, DynamicModelListView):
    """Expone el listado de proyectos con filtros automáticos."""
    model = Project
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context
    
class ProjectCreateView(LoginRequiredMixin, CreateView):
    """Formulario para crear proyectos con atributos temporales necesarios."""
    model = Project
    form_class = ProjectAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('project-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        return context

class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza proyectos y reusa la plantilla de formulario base."""
    model = Project
    form_class = ProjectAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('project-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context
    
class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """Confirma la eliminación de un proyecto mostrando su nombre."""
    model = Project
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('project-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'project-list'
        return context

############################# Client Views ###########################

class ClientListView(LoginRequiredMixin, DynamicModelListView):
    """Lista clientes utilizando los filtros dinámicos heredados."""
    model = ClientCompany
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context
    
class ClientCreateView(LoginRequiredMixin, CreateView):
    """Creación guiada de clientes con campos de fecha y lista relacionada."""
    model = ClientCompany
    form_class = ClientAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('clientcompany-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        return context

class ClientUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza clientes y conserva el comportamiento de formularios estándar."""
    model = ClientCompany
    form_class = ClientAssetsForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('clientcompany-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context
    
class ClientDeleteView(LoginRequiredMixin, DeleteView):
    """Elimina un cliente después de confirmar sus datos básicos."""
    model = ClientCompany
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('clientcompany-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'clientcompany-list'
        return context

############################ Evaluation Views ###########################

def get_objects_by_type(request):
    """Devuelve instancias de un modelo dado para llenar selects vía AJAX."""
    # Check if the request is an AJAX request
    content_type_id = request.GET.get('type_id')
    ct = ContentType.objects.get(id=content_type_id)
    model_class = ct.model_class()

    data = []
    for obj in model_class.objects.all():
        data.append({'id': obj.id, 'name': str(obj)})

    return JsonResponse({'objects': data})


def crear_evaluacion(request):
    """Prepara y procesa el formulario para generar una evaluación de riesgo."""
    
    model_types = ContentType.objects.filter(model__in=[
        'informationassets', 'vendor', 'project', 'clientcompany'
    ])
    model_choices = []

    for ct in model_types:
        model_choices.append({
            'id': ct.id,
            'name': ct.model_class()._meta.verbose_name.title()
        })

    # allow pre-filling from GET (e.g., after a Treatment was implemented)
    type_id = request.GET.get('type_id') or request.GET.get('model_type')
    object_id = request.GET.get('object_id')
    from_treatment = request.GET.get('from_treatment')
    intel_item_id = request.GET.get('intel_item_id')

    if request.method == 'POST':
        form = RiskEvaluationForm(request.POST)
        if form.is_valid():
            evaluacion = form.save()
            return redirect('evaluation-detail', pk=evaluacion.pk)
        else:
            # Surface validation errors to user
            messages.error(request, 'Errores en el formulario: ' + '; '.join(
                [f"{k}: {', '.join(map(str,v))}" for k,v in form.errors.items()]
            ))
    else:
        initial = {}
        form = RiskEvaluationForm()
        # If intel_item_id provided, attempt mapping to resources.Threat even when no type_id
        if intel_item_id and IntelThreatLink is not None and IntelItem is not None:
            try:
                intel = IntelItem.objects.get(pk=int(intel_item_id))
                link = IntelThreatLink.objects.filter(intel_item=intel).select_related('resources_threat').first()
                if link:
                    initial['threat'] = link.resources_threat.pk
                else:
                    possible = Threat.objects.filter(name__iexact=(getattr(intel, 'title', '') or '')).first()
                    if possible:
                        IntelThreatLink.objects.create(
                            intel_item=intel,
                            resources_threat=possible,
                            match_type='auto',
                            created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                        )
                        initial['threat'] = possible.pk
                    else:
                        new_th = Threat.objects.create(name=(getattr(intel, 'title', None) or f"IntelItem {intel.pk}"), description=(getattr(intel, 'description', '') or ''), type_threat=ThreatType.THREAT_INTEL)
                        IntelThreatLink.objects.create(
                            intel_item=intel,
                            resources_threat=new_th,
                            match_type='auto',
                            created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                        )
                        initial['threat'] = new_th.pk
            except Exception:
                # Fail silently on mapping errors but keep flow
                pass
        # If type_id provided, restrict choices for object_id to that model
        if type_id:
            try:
                ct = ContentType.objects.get(pk=type_id)
                model_class = ct.model_class()
                # build choices for object_id field
                choices = [(str(obj.pk), str(obj)) for obj in model_class.objects.all()]
                form.fields['object_id'].choices = choices
                initial['model_type'] = ct.pk
                if object_id:
                    # ensure provided object_id is in choices
                    initial['object_id'] = str(object_id)
                # prefill description if from_treatment
                if from_treatment:
                    form_desc = f"Re-evaluación iniciada desde tratamiento #{from_treatment}."
                    initial['description'] = form_desc

                # If arriving from threat_intel, try to map intel item -> resources.Threat
                if intel_item_id and IntelThreatLink is not None and IntelItem is not None:
                    try:
                        intel = IntelItem.objects.get(pk=int(intel_item_id))
                        # Look for existing link
                        link = IntelThreatLink.objects.filter(intel_item=intel).select_related('resources_threat').first()
                        if link:
                            initial['threat'] = link.resources_threat.pk
                        else:
                            # Try to auto-match by exact name
                            possible = Threat.objects.filter(name__iexact=(getattr(intel, 'title', '') or '')).first()
                            if possible:
                                IntelThreatLink.objects.create(
                                    intel_item=intel,
                                    resources_threat=possible,
                                    match_type='auto',
                                    created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                                )
                                initial['threat'] = possible.pk
                            else:
                                # create a new resources.Threat and link it
                                new_th = Threat.objects.create(name=(getattr(intel, 'title', None) or f"IntelItem {intel.pk}"), description=(getattr(intel, 'description', '') or ''))
                                IntelThreatLink.objects.create(
                                    intel_item=intel,
                                    resources_threat=new_th,
                                    match_type='auto',
                                    created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                                )
                                initial['threat'] = new_th.pk
                    except IntelItem.DoesNotExist:
                        pass
                # recreate form with initial
                form = RiskEvaluationForm(initial=initial)
                form.fields['object_id'].choices = choices
            except ContentType.DoesNotExist:
                pass

    return render(request, 'evaluacion_form.html', {
        'form': form,
        'model_types': model_types,
        'related_links': [
            (reverse('evaluation-list'), 'Lista de evaluaciones'),
            (reverse('checklist-templates'), 'Plantillas de checklist'),
        ],
    })

class RiskEvaluationDetailView(DetailView):
    """Muestra la evaluación de riesgo y los campos del objeto evaluado."""
    model = RiskEvaluation
    template_name = 'evaluation_detail.html'
    context_object_name = 'evaluation'  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluated = self.object.evaluated_object

        # Obtener campos comunes del objeto evaluado (heredado de RiskEvaluableObject)
        base_fields = []
        for field in evaluated._meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['updated']:
                value = getattr(evaluated, field.name, None)

                if field.choices:
                    display_method = f"get_{field.name}_display"
                    value = getattr(evaluated, display_method, lambda: value)()

                base_fields.append({
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['evaluated_fields'] = base_fields
        return context


@login_required
@require_POST
def force_create_treatment(request, pk):
    """Genera manualmente un tratamiento vinculado a una evaluación específica."""
    evaluation = get_object_or_404(RiskEvaluation, pk=pk)

    if evaluation.treatment is not None:
        messages.info(request, 'La evaluación ya tiene un tratamiento asociado.')
        return redirect('evaluation-detail', pk=pk)
    try:
        treatment = Treatment.objects.create(
            name=f"Tratamiento forzado para evaluación {evaluation.pk}",
            treatment_type=TypeTreatment.REDUCE,
            description=f"Tratamiento creado manualmente desde la evaluación #{evaluation.pk}.",
            controls=Controls.A5_INFORMATION_SECURITY_POLICIES,
            content_type=evaluation.evaluated_type,
            object_id=evaluation.evaluated_id,
            deadline=timezone.now().date() + timedelta(days=30),
            treatment_responsible=CustomUser.for_current_tenant().first(),
            treatment_oportunity=TreatmentOportunity.PREVENTIVE,
            application_periodicity=ApplicationPeriodicity.PERMANENT,
            control_automation=ControlAutomation.MANUAL,
            priority=Priority.NO_PRIORITY,
        )

        # link evaluation -> treatment
        evaluation.treatment = treatment
        evaluation.save(update_fields=['treatment'])

        messages.success(request, 'Tratamiento forzado creado y vinculado correctamente.')
    except Exception as e:
        messages.error(request, f'No se pudo crear el tratamiento: {e}')

    return redirect('evaluation-detail', pk=pk)
    
class RiskEvaluationListView(LoginRequiredMixin, ListView):
    """Lista las evaluaciones de riesgo con filtros por nivel y tratamiento."""
    model = RiskEvaluation
    template_name = 'evaluation_list.html'
    context_object_name = 'evaluations'
    fields = model._meta.fields  
    login_url = 'login'
    EXCLUDED_FIELDS = ['updated', 'id']

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related('treatment')
            .order_by(
                F('treatment__stage').asc(nulls_last=True),
                F('treatment__deadline').asc(nulls_last=True),
                'id'
            )
        )

        # Filter by risk level if provided in GET params
        risk = self.request.GET.get('risk')
        if risk is not None and risk != '':
            try:
                risk_val = int(risk)
                qs = qs.filter(risk_level=risk_val)
            except ValueError:
                pass

        # If not_implemented=1, only include evaluations that have a treatment
        # whose stage is different from IMPLEMENTED
        not_impl = self.request.GET.get('not_implemented')
        if str(not_impl) in ('1', 'true', 'True'):
            # Return evaluations that have a treatment and are NOT in IMPLEMENTED stage
            qs = qs.filter(treatment__isnull=False).exclude(treatment__stage=TreatmentStage.IMPLEMENTED)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.model
        fields = model._meta.fields
         # Campos mostrado
        context['fields'] = [
            {'name': field.name, 'verbose': field.verbose_name.title()}
            for field in self.fields if field.name not in self.EXCLUDED_FIELDS
        ]
        
        # Filtros: choices, booleanos, foreign keys
        filters = {}

        for field in fields:
            if field.name in self.EXCLUDED_FIELDS:
                continue

            # Campos con choices
            if field.choices:
                filters[field.name] = [{'value': c[1], 'label': c[1]} for c in field.choices]

            # BooleanField
            elif isinstance(field, models.BooleanField):
                filters[field.name] = [
                    {'value': 'True', 'label': 'Sí'},
                    {'value': 'False', 'label': 'No'},
                ]

            # ForeignKey
            elif isinstance(field, models.ForeignKey):
                related = field.related_model.objects.all()
                filters[field.name] = [{'value': str(obj.pk), 'label': str(obj)} for obj in related]
            
            # si es datetime o date, solo marcamos el tipo
            elif isinstance(field, models.DateField) or isinstance(field, models.DateTimeField):
                filters[field.name] = {'type': 'date'}  # Sólo marcamos que es tipo fecha

        context['dynamic_filters'] = filters
        context['verbose_name_plural'] = model._meta.verbose_name_plural.title()
        

        context['verbose_name_plural'] = self.model._meta.verbose_name_plural.title()
        context['create_view'] = 'evaluation-create'
        context['detail_view'] = 'evaluation-detail'
        context['delete_view'] = 'evaluation-delete'
        return context
   
class RiskEvaluationDeleteView(LoginRequiredMixin, DeleteView):
    """Elimina evaluaciones de riesgo tras mostrar una confirmación."""
    model = RiskEvaluation
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('evaluation-list') 
    login_url = 'login'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'evaluation-list'
        return context


############################ Treatment Views ###########################

class TreatmentListView(LoginRequiredMixin, DynamicModelListView):
    """Lista tratamientos con filtros por etapa y vista dinámica."""
    model = Treatment
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context

    def get_queryset(self):
        qs = super().get_queryset()

        stage = self.request.GET.get('stage')
        if stage is not None and stage != '':
            try:
                stage_val = int(stage)
                qs = qs.filter(stage=stage_val)
            except ValueError:
                pass

        return qs

def crear_tratamiento(request):
    """Gestiona el formulario para crear un tratamiento asociado a un recurso."""
    model_types = ContentType.objects.filter(model__in=[
        'informationassets', 'vendor', 'project', 'clientcompany'
    ])
    
    if request.method == 'POST':
        
        form = TreatmentForm(data=request.POST)

        if form.is_valid():
            
            model_type = form.cleaned_data.get('model_type')
            object_id = form.cleaned_data.get('object_id')

            treatment = form.save(commit=False)

            if model_type and object_id:
                treatment.content_type = model_type
                treatment.object_id = int(object_id)

            treatment.save()
            
            return redirect('treatment-detail', pk=treatment.pk)
        else:
            messages.error(request, "Formulario inválido.")
            logger.warning("Formulario inválido en crear_tratamiento para user %s", request.user)
            # Mostramos los choices que están cargados para el select
    else:
        form = TreatmentForm()
        

    return render(request, 'treatment-create.html', {
        'form': form,
        'model_types': model_types,
        'related_links': [
            (reverse('treatment-list'), 'Lista de tratamientos'),
            (reverse('checklist-templates'), 'Plantillas de checklist'),
        ],
    })


    

class TreatmentDeleteView(LoginRequiredMixin, DeleteView):
    """Borra un tratamiento después de confirmar su contexto."""
    model = Treatment
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('treatment-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'treatment-list'
        return context
    

class TreatmentUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza los detalles del tratamiento y registra cambios de etapa."""
    model = Treatment
    form_class = TreatmentForm
    template_name = 'treatment-create.html'
    success_url = reverse_lazy('treatment-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context
    
    def form_valid(self, form):
        model_type = form.cleaned_data.get('model_type')
        object_id = form.cleaned_data.get('object_id')

        if model_type and object_id:
            form.instance.content_type = model_type
            form.instance.object_id = int(object_id)

        # Capture previous stage to detect changes made via the form
        old_stage = None
        if hasattr(self, 'object') and self.get_object():
            try:
                old_stage = self.get_object().stage
            except Exception:
                old_stage = None

        # If stage changed via the form, use the model helper to record timestamp/user
        new_stage = form.cleaned_data.get('stage', None)

        if old_stage is not None and new_stage is not None and new_stage != old_stage:
            # Apply form changes without committing so `form.instance` has the new values
            form.save(commit=False)
            try:
                user = self.request.user if getattr(self.request, 'user', None) and self.request.user.is_authenticated else None
                form.instance.set_stage(new_stage, user=user)
            except Exception:
                # Fallback: if set_stage fails, attempt the previous behavior
                try:
                    form.instance.stage_changed_at = timezone.now()
                    if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
                        form.instance.stage_changed_by = self.request.user
                    form.instance.save(update_fields=['stage_changed_at', 'stage_changed_by'])
                except Exception:
                    pass
            # Now persist the rest of the form (this will not overwrite stage_changed_* fields)
            response = super().form_valid(form)
        else:
            response = super().form_valid(form)

        messages.success(self.request, "Tratamiento actualizado con éxito.")
        return response
    

def test_colreorder(request):
    """Renderiza una tabla de prueba con columnas reordenables."""
    return render(request, 'test_table.html')


class ClientListView(LoginRequiredMixin, DynamicModelListView):
    """Lista clientes con filtros automáticos reutilizando la vista dinámica."""
    model = ClientCompany
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context
    
class ThreatCreateView(LoginRequiredMixin, CreateView):
    """Permite crear amenazas y mantener los campos de descripción."""
    model = Threat
    form_class = ThreatForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('threat-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        return context


class ThreatListView(LoginRequiredMixin, DynamicModelListView):
    """Expone el listado de amenazas con metadatos dinámicos."""
    model = Threat
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context
    
class ThreatUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza una amenaza manteniendo el contexto original."""
    model = Threat
    form_class = ThreatForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('threat-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context
    
class ThreatDetailView(LoginRequiredMixin, DetailView):
    """Detalle para una amenaza con campos visibles y enlaces auxiliares."""
    model = Threat
    template_name = 'detail-resource.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        meta = obj.__class__._meta

        context['verbose_model_name'] = meta.verbose_name.title()

        # Campos visibles (excluyendo ID, campos sensibles o FK pesados si querés)
        visible_fields = []
        for field in meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id', 'password']:
                if field.choices:
                    display_method = f"get_{field.name}_display"
                    value = getattr(obj, display_method)()
                else:
                    value = getattr(obj, field.name, None)

                visible_fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['fields'] = visible_fields
        # URLs auxiliares
        model_name = meta.model_name
        try:
            context['edit_url'] = reverse(f'{model_name}-update', args=[obj.pk])
            context['delete_url'] = reverse(f'{model_name}-delete', args=[obj.pk])
            context['back_url'] = reverse(f'{model_name}-list')
        except:
            context['edit_url'] = None
            context['delete_url'] = None
            context['back_url'] = '#'

        return context
    
class ThreatDeleteView(LoginRequiredMixin, DeleteView):
    """Elimina una amenaza tras confirmar sus datos."""
    model = Threat
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('threat-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'threat-list'
        return context


class VulnerabilityListView(LoginRequiredMixin, DynamicModelListView):
    """Lista vulnerabilidades con filtros automáticos similares a otras vistas."""
    model = Vulnerability
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context
    
class VulnerabilityCreateView(LoginRequiredMixin, CreateView):
    """Formulario para crear vulnerabilidades con descripción detallada."""
    model = Vulnerability
    form_class = VulnerabilityForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('vulnerability-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Crear'
        return context
    
class VulnerabilityUpdateView(LoginRequiredMixin, UpdateView):
    """Actualiza vulnerabilidades reutilizando el mismo formulario."""
    model = Vulnerability
    form_class = VulnerabilityForm
    template_name = 'CU-resource.html'
    success_url = reverse_lazy('vulnerability-list')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        model_name = self.model._meta.model_name
        context['list_url_name'] = f'{model_name}-list'
        context['action_type'] = 'Editar'
        return context

class VulnerabilityDetailView(LoginRequiredMixin, DetailView):
    """Muestra los detalles de una vulnerabilidad y sus campos asociados."""
    model = Vulnerability
    template_name = 'detail-resource.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        meta = obj.__class__._meta

        context['verbose_model_name'] = meta.verbose_name.title()

        # Campos visibles (excluyendo ID, campos sensibles o FK pesados si querés)
        visible_fields = []
        for field in meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id', 'password']:
                if field.choices:
                    display_method = f"get_{field.name}_display"
                    value = getattr(obj, display_method)()
                else:
                    value = getattr(obj, field.name, None)

                visible_fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['fields'] = visible_fields
        # URLs auxiliares
        model_name = meta.model_name
        try:
            context['edit_url'] = reverse(f'{model_name}-update', args=[obj.pk])
            context['delete_url'] = reverse(f'{model_name}-delete', args=[obj.pk])
            context['back_url'] = reverse(f'{model_name}-list')
        except:
            context['edit_url'] = None
            context['delete_url'] = None
            context['back_url'] = '#'

        return context

class VulnerabilityDeleteView(LoginRequiredMixin, DeleteView):
    """Elimina una vulnerabilidad luego de confirmar su contexto."""
    model = Vulnerability
    template_name = 'delete-resource.html'
    success_url = reverse_lazy('vulnerability-list') 
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verbose_name'] = capfirst(self.model._meta.verbose_name)
        context['verbose_name_plural'] = capfirst(self.model._meta.verbose_name_plural)
        context['list_view'] = 'vulnerability-list'
        return context


@login_required
@require_POST
def advance_treatment_stage(request, pk):
    """Avanza la etapa de un tratamiento y guarda notas complementarias opcionales."""
    treatment = get_object_or_404(Treatment, pk=pk)

    # Permission: only staff, superuser or responsible user
    user = request.user
    if not (user.is_staff or user.is_superuser or (treatment.treatment_responsible and treatment.treatment_responsible == user)):
        messages.error(request, "No tienes permiso para cambiar la etapa de este tratamiento.")
        return redirect('treatment-detail', pk=pk)

    try:
        new_stage = int(request.POST.get('stage'))
    except (TypeError, ValueError):
        messages.error(request, "Etapa inválida.")
        return redirect('treatment-detail', pk=pk)

    # Optional notes
    analysis_notes = request.POST.get('analysis_notes')
    immediate_actions = request.POST.get('immediate_actions')
    corrective_actions = request.POST.get('corrective_actions')

    if analysis_notes is not None:
        treatment.analysis_notes = analysis_notes
    if immediate_actions is not None:
        treatment.immediate_actions = immediate_actions
    if corrective_actions is not None:
        treatment.corrective_actions = corrective_actions

    treatment.set_stage(new_stage, user=user)

    messages.success(request, f"Etapa actualizada a {treatment.get_stage_display()}.")
    return redirect('treatment-detail', pk=pk)


class ChecklistTemplateListView(LoginRequiredMixin, ListView):
    """Lista las plantillas de checklist disponibles para asignar a recursos."""
    model = ChecklistTemplate
    template_name = 'checklist_templates_list.html'
    login_url = 'login'


class ChecklistTemplateCreateView(LoginRequiredMixin, CreateView):
    """Permite crear plantillas de checklist y navegar hacia listas relacionadas."""
    model = ChecklistTemplate
    form_class = ChecklistTemplateForm
    template_name = 'checklist_template_form.html'
    success_url = reverse_lazy('checklist-templates')
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_links'] = [
            (reverse('checklist-templates'), 'Lista de plantillas'),
            (reverse('vendor-list'), 'Proveedores'),
        ]
        return context


class VendorEvaluationCreateView(LoginRequiredMixin, CreateView):
    """Formulario para ingresar evaluaciones de proveedores y registrar responsables."""
    model = VendorEvaluation
    form_class = VendorEvaluationForm
    template_name = 'vendor_evaluation_form.html'
    login_url = 'login'

    def get_success_url(self):
        return reverse_lazy('vendor-evaluation-detail', args=[self.object.pk])

    def form_valid(self, form):
        obj = form.save(commit=False)
        if not obj.performed_by:
            obj.performed_by = self.request.user
        obj.save()
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        # allow prefilling vendor via ?vendor=<pk>
        vendor_pk = self.request.GET.get('vendor')
        if vendor_pk:
            initial['vendor'] = vendor_pk
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['related_links'] = [
            (reverse('vendor-list'), 'Lista de proveedores'),
            (reverse('checklist-templates'), 'Plantillas de checklist'),
        ]
        return ctx


class VendorEvaluationDetailView(LoginRequiredMixin, DetailView):
    """Detalle de evaluación con posibilidad de editar ítems y marcar completada."""
    model = VendorEvaluation
    template_name = 'vendor_evaluation_detail.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluation = self.get_object()
        queryset = evaluation.items.all()
        formset = VendorEvaluationItemFormSet(queryset=queryset)
        context['formset'] = formset
        # related links for quick navigation
        try:
            context['related_links'] = [
                (reverse('vendor-list'), 'Lista de proveedores'),
                (reverse('vendor-evaluation-create') + f'?vendor={evaluation.vendor.pk}', 'Nueva evaluación para proveedor'),
            ]
        except Exception:
            context['related_links'] = []
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = VendorEvaluationItemFormSet(request.POST, queryset=self.object.items.all())
        if formset.is_valid():
            formset.save()
            if request.POST.get('mark_completed'):
                self.object.status = VendorEvaluationStatus.COMPLETED
                self.object.performed_at = timezone.now()
                if not self.object.performed_by:
                    self.object.performed_by = request.user
                self.object.save()
                next_eval = self.object.vendor.schedule_next_evaluation(
                    from_date=self.object.scheduled_date
                )
                if next_eval:
                    messages.success(request, f'Se programó una nueva evaluación pendiente para {next_eval.scheduled_date}')
                messages.success(request, 'Evaluación marcada como completada y guardada correctamente')
            else:
                messages.success(request, 'Evaluación guardada correctamente')
            return redirect(reverse('vendor-evaluation-detail', args=[self.object.pk]))
        else:
            context = self.get_context_data()
            context['formset'] = formset
            return render(request, self.template_name, context)


def get_pending_evaluations_queryset(user, include_all=False):
    """Construye el queryset de evaluaciones pendientes, opcionalmente para todos los usuarios."""
    qs = VendorEvaluation.objects.filter(
        status=VendorEvaluationStatus.PENDING,
        scheduled_date__isnull=False,
    ).select_related('vendor').order_by('scheduled_date')
    if include_all:
        return qs
    return qs.filter(vendor__owner=user)


def _reminder_lead_days_for_request(request):
    """Obtiene los días de anticipación para recordatorios desde la configuración del tenant."""
    tenant = getattr(request, 'tenant', None)
    reminder_days = None
    if tenant:
        settings_obj = getattr(tenant, 'settings', None)
        if settings_obj is None:
            settings_obj = TenantSettings.for_client(getattr(tenant, 'id', None))
        if settings_obj:
            reminder_days = settings_obj.reminder_lead_days
    return reminder_days if reminder_days is not None else 14


def build_pending_evaluations_context(request, queryset):
    """Construye el contexto de evaluaciones pendientes con banderas de recordatorio."""
    reminder_days = _reminder_lead_days_for_request(request)
    pending = list(queryset) if queryset is not None else []
    for evaluation in pending:
        evaluation.can_perform_evaluation = evaluation.can_be_performed(reminder_days)
    return {
        'pending_evaluations': pending,
        'reminder_lead_days': reminder_days,
    }


class VendorEvaluationPendingOwnerListView(LoginRequiredMixin, ListView):
    """Lista evaluaciones pendientes para el dueño o el staff, con contexto de recordatorios."""
    model = VendorEvaluation
    template_name = 'vendor_evaluation_pending_list.html'
    context_object_name = 'pending_evaluations'
    login_url = 'login'

    def get_queryset(self):
        include_all = self.request.user.is_staff or self.request.user.is_superuser
        return get_pending_evaluations_queryset(self.request.user, include_all=include_all)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_qs = context.get('pending_evaluations') or self.get_queryset()
        context.update(build_pending_evaluations_context(self.request, pending_qs))
        return context


def checklist_template_detail(request, pk):
    """Ver y editar una plantilla y sus items (inline formset)."""
    template = get_object_or_404(ChecklistTemplate, pk=pk)
    ChecklistItemFormSet = inlineformset_factory(ChecklistTemplate, ChecklistItem, form=ChecklistItemForm, extra=1, can_delete=True)

    if request.method == 'POST':
        form = ChecklistTemplateForm(request.POST, instance=template)
        formset = ChecklistItemFormSet(request.POST, instance=template)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Plantilla y items guardados correctamente')
            return redirect('checklist-templates')
    else:
        form = ChecklistTemplateForm(instance=template)
        formset = ChecklistItemFormSet(instance=template)

    return render(request, 'checklist_template_detail.html', {
        'form': form,
        'formset': formset,
        'object': template,
        'related_links': [
            (reverse('checklist-templates'), 'Volver a plantillas'),
            (reverse('checklist-template-create'), 'Crear nueva plantilla'),
        ],
    })


class VendorChecklistCreateView(LoginRequiredMixin, CreateView):
    """Asigna o actualiza la checklist de seguridad asociada a un proveedor."""
    model = VendorChecklist
    form_class = VendorChecklistForm
    template_name = 'vendor_checklist_form.html'
    success_url = reverse_lazy('vendor-list')
    login_url = 'login'

    def form_valid(self, form):
        vendor = form.cleaned_data['vendor']
        template = form.cleaned_data['template']
        customized = form.cleaned_data.get('customized', False)
        notes = form.cleaned_data.get('notes') or ''
        assignment_qs = VendorChecklist.objects.filter(vendor=vendor).order_by('-updated')
        assignment = assignment_qs.first()
        created = False
        if assignment:
            assignment.template = template
            assignment.customized = customized
            assignment.notes = notes
            assignment.save()
        else:
            assignment = VendorChecklist.objects.create(
                vendor=vendor,
                template=template,
                customized=customized,
                notes=notes,
            )
            created = True
        VendorChecklist.objects.filter(vendor=vendor).exclude(pk=assignment.pk).delete()
        self.object = assignment
        action = 'asignada' if created else 'actualizada'
        messages.success(self.request, f'Checklist {action} al proveedor correctamente')
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        # allow prefilling from query params: ?vendor=<pk>&template=<pk>
        v = self.request.GET.get('vendor')
        t = self.request.GET.get('template')
        if v:
            initial['vendor'] = v
        if t:
            initial['template'] = t
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['related_links'] = [
                (reverse('vendor-list'), 'Lista de proveedores'),
                (reverse('checklist-templates'), 'Plantillas de checklist'),
            ]
        except Exception:
            ctx['related_links'] = []
        return ctx
