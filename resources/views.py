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
    TreatmentStage,
    TypeTreatment,
    Controls,
    TreatmentOportunity,
    ApplicationPeriodicity,
    ControlAutomation,
    Priority,
)
from .forms import InformationAssetsForm, ProjectAssetsForm, RiskEvaluationForm, ThreatForm, TreatmentForm, VendorForm, ClientAssetsForm, VulnerabilityForm
from django.utils.text import capfirst
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Q
import logging
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from login.models import CustomUser


# Create your views here.

logger = logging.getLogger(__name__)
################################### Asset Views ###########################

class DynamicModelListView(ListView):
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
        return context

    

class AssetListView(LoginRequiredMixin, DynamicModelListView):
    model = InformationAssets
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model._meta.model_name}-create'
        context['update_view'] = f'{self.model._meta.model_name}-update'
        context['delete_view'] = f'{self.model._meta.model_name}-delete'
        context['detail_view'] = f'{self.model._meta.model_name}-detail'
        return context


class AssetCreateView(LoginRequiredMixin, CreateView):
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
        return context

class AssetUpdateView(LoginRequiredMixin, UpdateView):
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
        return context

class AssetDetailView(LoginRequiredMixin, DetailView):
    model=InformationAssets
    template_name = 'detail-resource.html'
    login_url = 'login'

class GenericResourceDetailView(DetailView):
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

        return context



class AssetDeleteView(LoginRequiredMixin, DeleteView):
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

class VendorUpdateView(LoginRequiredMixin, UpdateView):
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
    model=Vendor
    template_name = 'detail-vendor.html'
    login_url = 'login'

class VendorDeleteView(LoginRequiredMixin, DeleteView):
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
    # Check if the request is an AJAX request
    content_type_id = request.GET.get('type_id')
    ct = ContentType.objects.get(id=content_type_id)
    model_class = ct.model_class()

    data = []
    for obj in model_class.objects.all():
        data.append({'id': obj.id, 'name': str(obj)})

    return JsonResponse({'objects': data})


def crear_evaluacion(request):
    
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

    if request.method == 'POST':
        form = RiskEvaluationForm(request.POST)
        if form.is_valid():
            evaluacion = form.save()
            return redirect('evaluation-detail', pk=evaluacion.pk)
    else:
        initial = {}
        form = RiskEvaluationForm()
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
                # recreate form with initial
                form = RiskEvaluationForm(initial=initial)
                form.fields['object_id'].choices = choices
            except ContentType.DoesNotExist:
                pass

    return render(request, 'evaluacion_form.html', {
        'form': form,
        'model_types': model_types,
    })

class RiskEvaluationDetailView(DetailView):
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
    """Force creation of a Treatment for the given RiskEvaluation and link them.

    This bypasses the automatic restriction (only moderate+ risk) and ensures the
    created Treatment is assigned to the evaluation so the relation exists.
    """
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
    """List view for Risk Evaluations"""
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
    })


    

class TreatmentDeleteView(LoginRequiredMixin, DeleteView):
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
    return render(request, 'test_table.html')


class ClientListView(LoginRequiredMixin, DynamicModelListView):
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
    """Advance or change the stage of a Treatment. Expects POST with 'stage' and optional notes fields."""
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