from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, JsonResponse
from .models import InformationAssets, Vendor, Proyect
from .forms import InformationAssetsForm, VendorForm
from django.utils.text import capfirst
# Create your views here.

class DynamicModelListView(ListView):
    template_name = 'model_list.html'  # Plantilla genérica
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
    #template_name = 'list-asset.html'
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
    success_url = reverse_lazy('asset-list')
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
    success_url = reverse_lazy('asset-list')
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
    template_name = 'detail-asset.html'
    login_url = 'login'


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = InformationAssets
    template_name = 'delete-asset.html'
    success_url = reverse_lazy('asset-list') 
    login_url = 'login'



class VendorListView(LoginRequiredMixin, ListView):
    model = Vendor
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_view'] = f'{self.model}-create'
        context['update_view'] = f'{self.model}-update'
        context['delete_view'] = f'{self.model}-delete'
        context['detail_view'] = f'{self.model}-detail'
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