from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, gestion_permisos, seleccionar_usuario #PermissionFormView, PermissionUserFormView,

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform1/',seleccionar_usuario, name='permissionform1'),
    path('permissionform2/<int:usuario_id>',gestion_permisos, name='permissionform2'),
]