from .views import AssetCreateView, AssetListView, AssetUpdateView, AssetDeleteView, AssetDetailView
from django.urls import path

urlpatterns = [
    path('asset-list/', AssetListView.as_view(), name='asset-list'),
    path('asset-create/', AssetCreateView.as_view(), name='asset-create'),
    path('asset-update/<int:pk>', AssetUpdateView.as_view(), name='asset-update'),
    path('asset-detail/<int:pk>', AssetDetailView.as_view(), name='asset-detail'),
    path('asset-delete/<int:pk>', AssetDeleteView.as_view(), name='asset-delete'),
]
