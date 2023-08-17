from django.contrib import admin
from django.urls import path
from passbase.views import ContrasListView, ContrasCreateView, ContrasUpdateView, ContrasDeleteView, SectionCreateView, SectionListView, SectionUpdateView, SectionDeleteView, SectionActiveView

urlpatterns = [
    
    path('listpass',ContrasListView.as_view(), name='listpass'),
    path('createpass',ContrasCreateView.as_view(), name='createpass'),
    path('editpass/<int:pk>', ContrasUpdateView.as_view(), name='updatepass'),
    path('deletepass/<int:pk>', ContrasDeleteView.as_view(), name='deletepass'),
    path('createsection',SectionCreateView.as_view(), name='createsection'),
    path('listsection',SectionListView.as_view(), name='listsection'),
    path('editsection/<int:pk>', SectionUpdateView.as_view(), name='updatesection'),
    path('activesection/<int:pk>', SectionActiveView.as_view(), name='activesection'),
    path('deletesection/<int:pk>', SectionDeleteView.as_view(), name='deletesection'),
    
]