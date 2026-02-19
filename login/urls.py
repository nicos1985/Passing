"""Rutas públicas y protegidas del login hub y tenant."""

from django.contrib import admin
from django.urls import path
from .views import CustomPasswordResetConfirmView, DepartureUser, GlobalSettingsUpdateView, LogoutFormView, CustomPasswordResetView ,UserListView, UserUpdateView, activate_superuser, activate_user, create_superuser, deactivate_user, resend_mail, recive_mail, UserDetailView, sso_consume, verify_2fa_sso, home_tenant, login_alias_to_home
from . import views 
from django.contrib.auth.views import  LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView, PasswordResetConfirmView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("", login_alias_to_home, name="login"),
    path('home/', views.home_tenant, name='home_tenant'),
    path('verify-2fa/',views.verify_2fa, name='verify_2fa'),
    path('show-qr-code-2fa/', views.show_qr_code_2fa, name='show-qr-code-2fa'),
    path('send-qr-email-for-user-ondemand/<int:pk>', views.send_qr_email_for_user_ondemand, name='send-qr-email-for-user-ondemand'),
    path('register/', views.register , name='register'),
    path('configuracion-global/<int:pk>', GlobalSettingsUpdateView.as_view() , name='configuracion-global'),
    path('<str:schema_name>/create-superuser/', create_superuser, name='create-superuser'),
    path('recive-mail/', recive_mail, name='recive-mail'),
    path('resend-mail/', resend_mail, name='resend-mail'),
    path('activate/<uidb64>/<token>/', activate_superuser, name='activate-superuser'),
    path('logout/', LogoutFormView.as_view(), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('reset-password/', PasswordResetView.as_view(template_name = 'password_reset.html'), name='password_reset'),
    path('reset-password/done/', PasswordResetDoneView.as_view(template_name='reset_password_done.html'), name='password_reset_done'),
    path('reset-password/confirm/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset-password/complete/', PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('users/', UserListView.as_view(), name='userlist' ),
    path('update-user/<int:pk>', UserUpdateView.as_view(), name='updateuser' ),
    path('detail-user/<int:pk>', UserDetailView.as_view(), name='detail-user' ),
    path('deactivate-user/<int:pk>', DepartureUser.as_view(), name='deactivateuser' ),
    path('activate-user/<int:pk>', activate_user, name='activateuser' ),
    #nuevo
    path("sso/consume/", sso_consume, name="sso_consume"),
    path("sso/verify-2fa/", verify_2fa_sso, name="verify_2fa_sso"),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)