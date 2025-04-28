from .views import AssetCreateView, AssetListView, AssetUpdateView, AssetDeleteView, AssetDetailView, RiskEvaluationDetailView, RiskEvaluationListView, TreatmentDeleteView, TreatmentListView, TreatmentUpdateView, VendorListView, VendorCreateView, VendorUpdateView, VendorDetailView, VendorDeleteView, GenericResourceDetailView, crear_evaluacion, crear_tratamiento, get_objects_by_type, RiskEvaluationDeleteView, test_colreorder
from .views import ProjectListView, ProjectCreateView, ProjectUpdateView, ProjectDeleteView
from .views import ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView
from .models import ClientCompany, InformationAssets, Treatment, Vendor, Project
from django.urls import path

urlpatterns = [
    # Asset URLs
    path('asset-list/', AssetListView.as_view(), name='informationassets-list'),
    path('asset-create/', AssetCreateView.as_view(), name='informationassets-create'),
    path('asset-update/<int:pk>', AssetUpdateView.as_view(), name='informationassets-update'),
    path('asset-detail/<int:pk>', GenericResourceDetailView.as_view(model=InformationAssets), name='informationassets-detail'),
    path('asset-delete/<int:pk>', AssetDeleteView.as_view(), name='informationassets-delete'),
    # Vulnerability URLs
    path('vendor-list/', VendorListView.as_view(), name='vendor-list'),
    path('vendor-create/', VendorCreateView.as_view(), name='vendor-create'),
    path('vendor-update/<int:pk>', VendorUpdateView.as_view(), name='vendor-update'),
    path('vendor-detail/<int:pk>', GenericResourceDetailView.as_view(model=Vendor), name='vendor-detail'),
    path('vendor-delete/<int:pk>', VendorDeleteView.as_view(), name='vendor-delete'),
    # Project URLs
    path('project-list/', ProjectListView.as_view(), name='project-list'),
    path('project-create/', ProjectCreateView.as_view(), name='project-create'),
    path('project-update/<int:pk>', ProjectUpdateView.as_view(), name='project-update'),
    path('project-detail/<int:pk>', GenericResourceDetailView.as_view(model=Project), name='project-detail'),
    path('project-delete/<int:pk>', ProjectDeleteView.as_view(), name='project-delete'),
    # Client Company URLs
    path('client-list/', ClientListView.as_view(), name='clientcompany-list'),
    path('client-create/', ClientCreateView.as_view(), name='clientcompany-create'),
    path('client-update/<int:pk>', ClientUpdateView.as_view(), name='clientcompany-update'),
    path('client-detail/<int:pk>', GenericResourceDetailView.as_view(model=ClientCompany), name='clientcompany-detail'),
    path('client-delete/<int:pk>', ClientDeleteView.as_view(), name='clientcompany-delete'),
    # Risk Evaluation URLs
    path('evaluation-create/', crear_evaluacion, name='evaluation-create'),
    path('ajax/get-objects/', get_objects_by_type, name='ajax-get-objects'),
    path('evaluation/<int:pk>/', RiskEvaluationDetailView.as_view(), name='evaluation-detail'),
    path('evaluation-list/', RiskEvaluationListView.as_view(), name='evaluation-list'),
    path('evaluation-delete/<int:pk>/', RiskEvaluationDeleteView.as_view(), name='evaluation-delete'),
    #TReatment URLs
    path('treatment-create/', crear_tratamiento, name='treatment-create'),
    path('treatment-list/', TreatmentListView.as_view(), name='treatment-list'),
    path('treatment-detail/<int:pk>', GenericResourceDetailView.as_view(model=Treatment), name='treatment-detail'),
    path('treatment-delete/<int:pk>', TreatmentDeleteView.as_view(), name='treatment-delete'),
    path('treatment-update/<int:pk>', TreatmentUpdateView.as_view(), name='treatment-update'),
    path('test-colreorder/', test_colreorder, name='test_colreorder'),
]