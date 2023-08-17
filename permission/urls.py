from django.contrib import admin
from django.urls import path
from permission.views import PermissionListView, PermissionFormView

urlpatterns = [
    
    path('permissionlist',PermissionListView.as_view(), name='permissionlist'),
    path('permissionform',PermissionFormView.as_view(), name='permissionform'),
]