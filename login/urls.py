from django.contrib import admin
from django.urls import path
from .views import LoginFormView, LogoutFormView, CustomPasswordResetView ,UserListView, UserUpdateView, deactivate_user
from . import views 
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView, PasswordResetConfirmView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    
    path('', LoginFormView.as_view(), name='login'),
    path('register/', views.register , name='register'),
    path('logout/', LogoutFormView.as_view(), name='logout'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('reset-password/', CustomPasswordResetView.as_view(template_name = 'password_reset.html'), name='password_reset'),
    path('reset-password/done/', PasswordResetDoneView.as_view(template_name='reset_password_done.html'), name='password_reset_done'),
    path('reset-password/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset-password/complete/', PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('users/', UserListView.as_view(), name='userlist' ),
    path('update-user/<int:pk>', UserUpdateView.as_view(), name='updateuser' ),
    path('deactivate-user/<int:pk>', deactivate_user, name='deactivateuser' ),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)