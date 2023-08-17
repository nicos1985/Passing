from django.contrib import admin
from django.urls import path
from .views import LoginFormView, LogoutFormView
from . import views
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
    
    path('register/', views.register , name='register'),
    path('login/', LoginFormView.as_view(), name='login'),
    path('logout/', LogoutFormView.as_view(), name='logout'),
]