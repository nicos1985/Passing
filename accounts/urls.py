"""URLs públicas del hub que inician login, Google OAuth y selección de tenant."""

from django.urls import path
from .views import google_start, google_start_auto, post_login_redirect, login_view, logout_view, choose_tenant_view

app_name = 'accounts'

urlpatterns = [
    path('', login_view, name='login'),
    path("logout/", logout_view, name="logout"),
    path("google/start-auto/", google_start_auto, name="google_start_auto"),
    path("google/start/", google_start, name="google_start"),
    path("post-login/", post_login_redirect, name="post_login"),
    path("choose-tenant/", choose_tenant_view, name="choose_tenant"),
]