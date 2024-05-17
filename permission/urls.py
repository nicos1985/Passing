from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, gestion_permisos, grant_permission, seleccionar_usuario #PermissionFormView, PermissionUserFormView,

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform1/',seleccionar_usuario, name='permissionform1'),
    path('permissionform2/<int:usuario_id>',gestion_permisos, name='permissionform2'),
    path('grantperm/<int:id_cont>/<int:id_user_share>/', grant_permission, name='grantperm'),
]