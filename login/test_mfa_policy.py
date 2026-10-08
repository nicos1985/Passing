from unittest.mock import patch

from django.test import RequestFactory
from django.core.management import call_command
from django.urls import Resolver404, resolve
from django_tenants.test.cases import TenantTestCase

from accounts.models import CustomUser, MultiFactorStatus, TenantSettings
from login.middleware import TwoFactorAuthMiddleware


class TenantMfaPolicyTests(TenantTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='mfa-user', email='mfa@example.test', password='test-password', client=self.tenant,
        )
        self.settings, _ = TenantSettings.objects.get_or_create(client=self.tenant)
        self.factory = RequestFactory()

    def _response(self, path='/monitoring/', session=None):
        request = self.factory.get(path)
        request.user = self.user
        request.tenant = self.tenant
        request.urlconf = 'passing.urls_tenant'
        request.session = session or {}
        with patch('login.middleware.messages.info'):
            return TwoFactorAuthMiddleware(lambda req: None)(request)

    def test_required_policy_redirects_to_enrollment_without_secret(self):
        self.settings.multifactor_status = MultiFactorStatus.REQUIRED
        self.settings.save(update_fields=['multifactor_status'])
        response = self._response()
        self.assertEqual(response.status_code, 302)
        self.assertIn('show-qr-code-2fa', response['Location'])

    def test_optional_policy_allows_user_without_2fa(self):
        self.settings.multifactor_status = MultiFactorStatus.OPTIONAL
        self.settings.save(update_fields=['multifactor_status'])
        self.assertIsNone(self._response())

    def test_required_policy_with_secret_routes_to_enrollment_until_confirmed(self):
        self.settings.multifactor_status = MultiFactorStatus.REQUIRED
        self.settings.save(update_fields=['multifactor_status'])
        self.user.otp_secret = 'JBSWY3DPEHPK3PXP'
        self.user.save(update_fields=['otp_secret'])
        self.assertIn('show-qr-code-2fa', self._response()['Location'])

    def test_verified_session_is_bound_to_user_and_tenant(self):
        self.settings.multifactor_status = MultiFactorStatus.REQUIRED
        self.settings.save(update_fields=['multifactor_status'])
        self.user.otp_secret = 'JBSWY3DPEHPK3PXP'
        self.user.is_2fa_enabled = True
        self.user.save(update_fields=['otp_secret', 'is_2fa_enabled'])
        session = {
            'is_2fa_verified': True,
            'twofa_verified_user_id': self.user.pk,
            'twofa_verified_client_id': self.tenant.pk + 1,
        }
        self.assertEqual(self._response(session=session).status_code, 302)
        session['twofa_verified_client_id'] = self.tenant.pk
        self.assertIsNone(self._response(session=session))

    def test_bootstrap_is_console_only(self):
        with self.assertRaises(Resolver404):
            resolve('/login/example/create-superuser/', urlconf='passing.urls_tenant')
        admin = CustomUser.objects.create_superuser(
            username='new-admin', email='new-admin@example.test', password='test-password',
        )
        call_command('link_tenant_superuser', self.tenant.schema_name, admin.username, verbosity=0)
        admin.refresh_from_db()
        self.assertEqual(admin.client_id, self.tenant.pk)
