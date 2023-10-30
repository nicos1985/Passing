from django.contrib import admin
from django.urls import path
from .views import LoginFormView, LogoutFormView, CustomPasswordResetView
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    
    path('register/', views.register , name='register'),
    path('login/', LoginFormView.as_view(), name='login'),
    path('logout/', LogoutFormView.as_view(), name='logout'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('reset-password/', CustomPasswordResetView.as_view(), name='password_reset'),
    #path('reset-password/done/', PasswordResetDoneView.as_view(), name='password_reset_done'),
    #path('reset-password/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    #path('reset-password/complete/', PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)