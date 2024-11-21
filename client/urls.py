from django.urls import path
from .views import client_register


urlpatterns = [
            path('client-register', client_register , name='client_register'),

            ]