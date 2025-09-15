from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from .views import client_register
from .debug_views import where_am_i  # si vive en passing.views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("__where/", where_am_i),
    path("accounts/", include("accounts.urls")),   # google_start, post-login, etc.
    path("accounts/", include("allauth.urls")),    # allauth
    path("client-register/", client_register, name="client_register"),
]

if settings.DEBUG:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
