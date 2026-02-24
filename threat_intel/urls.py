from django.urls import path
from . import views

app_name = 'threat_intel'

urlpatterns = [
    # Run views
    path('runs/', views.RunListView.as_view(), name='run-list'),
    path('runs/<int:pk>/', views.RunDetailView.as_view(), name='run-detail'),
    path('runs/<int:pk>/rerun/', views.RunRerunView.as_view(), name='run-rerun'),
    path('runs/<int:pk>/export/', views.RunExportView.as_view(), name='run-export'),
    
    # RunItem views
    path('runs/<int:run_pk>/items/', views.RunItemListView.as_view(), name='runitem-list'),
    
    # IntelItem views
    path('items/<int:pk>/', views.IntelItemDetailView.as_view(), name='item-detail'),
    path('items/<int:pk>/toggle-relevant/', views.IntelItemToggleRelevantView.as_view(), name='item-toggle-relevant'),
    path('items/<int:pk>/link-threat/', views.LinkThreatView.as_view(), name='link-threat'),
    path('ajax/search-threats/', views.search_threats_ajax, name='search-threats-ajax'),
    
    # AIAnalysis views
    path('analyses/', views.AIAnalysisListView.as_view(), name='analysis-list'),
    path('analyses/<int:pk>/', views.AIAnalysisDetailView.as_view(), name='analysis-detail'),
    path('analyses/<int:pk>/rerun/', views.AIAnalysisRerunView.as_view(), name='analysis-rerun'),
    path('analyses/<int:pk>/export/', views.AIAnalysisExportView.as_view(), name='analysis-export'),
    
    # Report views
    path('reports/', views.ReportListView.as_view(), name='report-list'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report-detail'),
    path('runs/<int:run_pk>/report/create/', views.ReportCreateView.as_view(), name='report-create'),
    path('reports/<int:pk>/send/', views.ReportSendView.as_view(), name='report-send'),
    
    # Review views
    path('runs/<int:run_pk>/items/<int:item_pk>/review/', views.ReviewCreateView.as_view(), name='review-create'),
    path('reviews/', views.ReviewListView.as_view(), name='review-list'),
    path('runs/<int:run_pk>/reviews/', views.ReviewListView.as_view(), name='review-list-run'),
    path('reviews/<int:pk>/', views.ReviewDetailView.as_view(), name='review-detail'),
    path('reviews/<int:pk>/edit/', views.ReviewUpdateView.as_view(), name='review-update'),
    
    # Configuration views
    path('config/', views.ConfigView.as_view(), name='config'),
    path('sources/', views.SourceListView.as_view(), name='source-list'),
    path('sources/<int:pk>/', views.SourceDetailView.as_view(), name='source-detail'),
    path('sources/create/', views.SourceCreateView.as_view(), name='source-create'),
    path('sources/<int:pk>/edit/', views.SourceUpdateView.as_view(), name='source-update'),
    path('techtags/', views.TechTagListView.as_view(), name='techtag-list'),
    path('techtags/<int:pk>/', views.TechTagDetailView.as_view(), name='techtag-detail'),
    path('techtags/create/', views.TechTagCreateView.as_view(), name='techtag-create'),
    path('techtags/<int:pk>/edit/', views.TechTagUpdateView.as_view(), name='techtag-update'),
]