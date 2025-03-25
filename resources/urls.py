from .views import AssetCreateView, AssetListView, AssetUpdateView, AssetDeleteView, AssetDetailView, VendorListView, VendorCreateView, VendorUpdateView, VendorDetailView, VendorDeleteView, GenericResourceDetailView
from .models import InformationAssets, Vendor
from django.urls import path

urlpatterns = [
    path('asset-list/', AssetListView.as_view(), name='informationassets-list'),
    path('asset-create/', AssetCreateView.as_view(), name='informationassets-create'),
    path('asset-update/<int:pk>', AssetUpdateView.as_view(), name='informationassets-update'),
    path('asset-detail/<int:pk>', GenericResourceDetailView.as_view(model=InformationAssets), name='informationassets-detail'),
    path('asset-delete/<int:pk>', AssetDeleteView.as_view(), name='informationassets-delete'),
    path('vendor-list/', VendorListView.as_view(), name='vendor-list'),
    path('vendor-create/', VendorCreateView.as_view(), name='vendor-create'),
    path('vendor-update/<int:pk>', VendorUpdateView.as_view(), name='vendor-update'),
    path('vendor-detail/<int:pk>', GenericResourceDetailView.as_view(model=Vendor), name='vendor-detail'),
    path('vendor-delete/<int:pk>', VendorDeleteView.as_view(), name='vendor-delete'),
]
