from django.conf import settings
from django.http import HttpResponseGone
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from passbase.access import superadmin_required


def home(request):
    return render(request, 'home.html')


@superadmin_required
def config(request):
    return render(request, 'admin.html')


@superadmin_required
@require_POST
def test_send_email(request):
    return HttpResponseGone('Las pruebas SMTP se ejecutan desde el servidor.')


@method_decorator(superadmin_required, name='dispatch')
class UpdateEmailConfigView(View):
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        return render(request, 'smtp_status.html', {
            'smtp_host': settings.EMAIL_HOST, 'smtp_port': settings.EMAIL_PORT,
            'smtp_tls': settings.EMAIL_USE_TLS,
        })
