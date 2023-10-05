from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, PermissionFormView, PermissionUserFormView

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform1/',PermissionUserFormView.as_view(), name='permissionform1'),
    path('permissionform2/',PermissionFormView.as_view(), name='permissionform2'),
]