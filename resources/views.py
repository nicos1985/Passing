from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse, JsonResponse
from .models import InformationAssets
from .forms import InformationAssetsUpdateForm, InformationAssetsCreateForm
# Create your views here.

class AssetListView(LoginRequiredMixin, ListView):
    model = InformationAssets
    template_name = 'list-asset.html'
    context_object_name = 'objects'
    login_url = 'login'

class AssetCreateView(LoginRequiredMixin, CreateView):
    model = InformationAssets
    form_class = InformationAssetsCreateForm
    template_name = 'create-asset.html'
    success_url = reverse_lazy('asset-list')
    login_url = 'login'

class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = InformationAssets
    form_class = InformationAssetsUpdateForm
    template_name = 'update-asset.html'
    success_url = reverse_lazy('asset-list')
    login_url = 'login'

class AssetDetailView(LoginRequiredMixin, DetailView):
    model=InformationAssets
    template_name = 'detail-asset.html'
    login_url = 'login'


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = InformationAssets
    template_name = 'delete-asset.html'
    success_url = reverse_lazy('asset-list') 
    login_url = 'login'

