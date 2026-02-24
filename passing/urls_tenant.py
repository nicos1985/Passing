"""passing URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from .views import home_tenant, test_send_email, UpdateEmailConfigView, set_language

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("i18n/setlang/", set_language, name="set_language"),
    path("login/", include("login.urls")),                
    path("resources/", include("resources.urls")),
    path("threat-intel/", include("threat_intel.urls")),
    path("pass/", include("passbase.urls")),
    path("notifications/", include("notifications.urls")),
    path("perm/", include("permission.urls")),
    path("test_send_email/", test_send_email, name="test_send_email"),
    path("update_email_config/", UpdateEmailConfigView.as_view(), name="update_email_config"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]