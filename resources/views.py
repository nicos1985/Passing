from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, JsonResponse
from .models import InformationAssets, RiskEvaluation, Vendor, Project, ClientCompany
from .forms import InformationAssetsForm, ProjectAssetsForm, RiskEvaluationForm, VendorForm, ClientAssetsForm
from django.utils.text import capfirst
from django.contrib.contenttypes.models import ContentType
# Create your views here.

class DynamicModelListView(ListView):
    template_name = 'list_resource.html'  # Plantilla genérica
    EXCLUDED_FIELDS = ['created', 'updated','id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.model
        fields = model._meta.fields

        
        # Creamos una lista de dicts con nombre interno y verbose
        context['fields'] = [
            {'name': field.name, 'verbose': field.verbose_name.title()}
            for field in fields if field.name not in self.EXCLUDED_FIELDS
        ]
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

    if request.method == 'POST':
        form = RiskEvaluationForm(request.POST)
        if form.is_valid():
            evaluacion = form.save()
            return redirect('evaluation-detail', pk=evaluacion.pk)
    else:
        form = RiskEvaluationForm()
        print(form.errors)

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
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id', 'created', 'updated']:
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
    
class RiskEvaluationListView(LoginRequiredMixin, ListView):
    model = RiskEvaluation
    template_name = 'evaluation_list.html'
    context_object_name = 'evaluations'
    fields = model._meta.fields  
    login_url = 'login'
    EXCLUDED_FIELDS = ['created', 'updated','id']


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fields'] = [
            {'name': field.name, 'verbose': field.verbose_name.title()}
            for field in self.fields if field.name not in self.EXCLUDED_FIELDS
        ]
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
