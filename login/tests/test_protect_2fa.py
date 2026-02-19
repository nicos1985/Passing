"""Tests que revisan que los correos de 2FA no filtren secretos."""

from django_tenants.test.cases import TenantTestCase
from django.test import override_settings
from django.core import mail
from django.contrib.auth import get_user_model
from login.views import send_qr_code_email_inline
from pathlib import Path

User = get_user_model()


class Protect2FATests(TenantTestCase):
    """Verifica que el QR y los correos de 2FA no expongan el secret."""
    def test_qr_template_does_not_reference_otp_secret(self):
        tpl = Path('templates/qr_2fa.html').read_text(encoding='utf-8')
        self.assertNotIn('{{ otp_secret', tpl)
        self.assertNotIn('}} otp_secret', tpl)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_qr_email_does_not_contain_secret(self):
        # create user and set otp_secret; TenantTestCase ensures tenant schemas exist
        user = User.objects.create(username='tuser', email='t@example.com')
        user.otp_secret = 'SOMESECRET1234'
        user.save()

        mail.outbox.clear()
        send_qr_code_email_inline(user)
        self.assertGreaterEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertNotIn('SOMESECRET1234', body)