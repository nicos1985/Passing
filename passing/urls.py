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
from django.contrib import admin
from django.urls import path, include
from . import views
from .views import test_send_email, home, config, UpdateEmailConfigView, client_register
from django.conf.urls.static import static

urlpatterns = [
    path('', home, name='home'),
    path('client-register/', client_register, name='client_register'),
    path('login/', include('login.urls') ),
    path('pass/',include('passbase.urls') ),
    path('notifications/',include('notifications.urls') ),
    path('perm/',include('permission.urls') ),
    path("__debug__/", include("debug_toolbar.urls")),
    path('test_send_email/', test_send_email, name='test_send_email'),
    path('update_email_config/', UpdateEmailConfigView.as_view(), name='update_email_config'),
    
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += path("__debug__/", include("debug_toolbar.urls")),

if settings.ADMIN_ENABLED:
    urlpatterns += [
        path('admin/', admin.site.urls),
    ]