"""URLs públicas del hub que inician login, Google OAuth y selección de tenant."""

from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from .views import google_start, google_start_auto, post_login_redirect, login_view, logout_view, choose_tenant_view
from .forms import HubPasswordResetForm

app_name = 'accounts'

urlpatterns = [
    path('', login_view, name='login'),
    path('login/', login_view, name='protected_login_alias'),
    path('password/reset/', RedirectView.as_view(
        pattern_name='accounts:password_reset', permanent=False,
    ), name='legacy_password_reset'),
    path('recover/', PasswordResetView.as_view(
        form_class=HubPasswordResetForm,
        template_name='accounts/recover_form.html',
        email_template_name='accounts/recover_email.txt',
        subject_template_name='accounts/recover_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),
    path('recover/done/', PasswordResetDoneView.as_view(
        template_name='accounts/recover_done.html',
    ), name='password_reset_done'),
    path('recover/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='accounts/recover_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('recover/complete/', PasswordResetCompleteView.as_view(
        template_name='accounts/recover_complete.html',
    ), name='password_reset_complete'),
    path("logout/", logout_view, name="logout"),
    path("google/start-auto/", google_start_auto, name="google_start_auto"),
    path("google/start/", google_start, name="google_start"),
    path("post-login/", post_login_redirect, name="post_login"),
    path("choose-tenant/", choose_tenant_view, name="choose_tenant"),
]