from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, gestion_permisos #PermissionFormView, PermissionUserFormView,

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform1/',gestion_permisos, name='permissionform1'),
    path('permissionform2/',gestion_permisos, name='permissionform2'),
]