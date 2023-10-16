from django.contrib import admin
from django.urls import path
from .views import LoginFormView, LogoutFormView
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    
    path('register/', views.register , name='register'),
    path('login/', LoginFormView.as_view(), name='login'),
    path('logout/', LogoutFormView.as_view(), name='logout'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)