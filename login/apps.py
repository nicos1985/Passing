from django.apps import AppConfig


class LoginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login'

    def ready(self):
        from . import session_policy  # noqa: F401 - register login signal

        # Device management must go through our audited recovery flow.
        from django.contrib import admin
        from django_otp.plugins.otp_static.models import StaticDevice
        from django_otp.plugins.otp_totp.models import TOTPDevice

        for model in (StaticDevice, TOTPDevice):
            if admin.site.is_registered(model):
                admin.site.unregister(model)
