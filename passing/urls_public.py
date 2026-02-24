from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from .views import client_register, landing
from .debug_views import where_am_i  # si vive en passing.views
from accounts.views import login_view as hub_login_view
from accounts.views import google_start_auto, google_start, post_login_redirect, choose_tenant_view

urlpatterns = [
    path("", landing, name="landing"),
    path("admin/", admin.site.urls),
    path("login/", hub_login_view, name="login"),
    # Aliases para rutas nombradas usadas en plantillas sin namespace
    path("accounts/google/start-auto/", google_start_auto, name="google_start_auto"),
    path("accounts/google/start/", google_start, name="google_start"),
    path("accounts/post-login/", post_login_redirect, name="post_login"),
    path("accounts/choose-tenant/", choose_tenant_view, name="choose_tenant_view"),
    path("__where/", where_am_i),
    path("accounts/", include("accounts.urls")),   # google_start, post-login, etc.
    path("accounts/", include("allauth.urls")),    # allauth
    path("client-register/", client_register, name="client_register"),
]

if settings.DEBUG:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
