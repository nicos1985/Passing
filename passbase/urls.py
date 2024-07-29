from django.contrib import admin
from django.urls import path
from passbase.views import ContrasListView, ContrasCreateView, ContrasUpdateView, ContrasDeleteView, DescargarArchivo, SectionCreateView, SectionListView, SectionUpdateView, SectionDeleteView, SectionActiveView, ContrasDetailView, denypermission, encrypt_all, encrypt_all_data, rollback_encryption
from passing.views import config
urlpatterns = [
    
    path('listpass',ContrasListView.as_view(), name='listpass'),
    path('config/', config, name='config'),
    path('detailpass/<int:pk>',ContrasDetailView.as_view(), name='detailpass'),
    path('createpass',ContrasCreateView.as_view(), name='createpass'),
    path('editpass/<int:pk>', ContrasUpdateView.as_view(), name='updatepass'),
    path('deletepass/<int:pk>', ContrasDeleteView.as_view(), name='deletepass'),
    path('createsection',SectionCreateView.as_view(), name='createsection'),
    path('listsection',SectionListView.as_view(), name='listsection'),
    path('editsection/<int:pk>', SectionUpdateView.as_view(), name='updatesection'),
    path('activesection/<int:pk>', SectionActiveView.as_view(), name='activesection'),
    path('deletesection/<int:pk>', SectionDeleteView.as_view(), name='deletesection'),
    path('downloadfile/<int:pk>', DescargarArchivo.as_view(), name='downloadfile'),
    path('denypermission/<int:pk>', denypermission, name='denypermission'),
    path('encrypt-all-data', encrypt_all_data, name='encryptall'),
    path('rollback-encryption', rollback_encryption, name='rollbackencryption'),
    
    
]