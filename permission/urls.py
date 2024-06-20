from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, PermissionRolesCreateView, gestion_permisos, grant_permission, seleccionar_usuario #PermissionFormView, PermissionUserFormView,

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform1/',seleccionar_usuario, name='permissionform1'),
    path('permissionform2/<int:usuario_id>',gestion_permisos, name='permissionform2'),
    path('grantperm/<int:id_cont>/<int:id_user_share>/<int:id_noti>/<str:id_user>', grant_permission, name='grantperm'),
    path('permissionroles-create',PermissionRolesCreateView.as_view(), name='permissionrolescreate'),

]