from django.urls import path
from two_factor.views import QRGeneratorView

from .mfa import MandatoryLoginView, MandatorySetupView, security_profile, reset_authenticator

app_name = 'two_factor'
urlpatterns = [
    path('login/', MandatoryLoginView.as_view(), name='login'),
    path('setup/', MandatorySetupView.as_view(), name='setup'),
    path('qr/', QRGeneratorView.as_view(), name='qr'),
    path('complete/', security_profile, name='setup_complete'),
    path('', security_profile, name='profile'),
    path('recover/<int:user_id>/', reset_authenticator, name='recover'),
]
