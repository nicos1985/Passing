from unittest.mock import patch

import pyotp
from django.test import RequestFactory
from django.core.management import call_command
from django.urls import Resolver404, resolve
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser, MultiFactorStatus, TenantMembership, TenantSettings
from accounts.utils import build_sso_token
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

    def test_sso_policy_blocks_authenticated_user_without_verified_otp(self):
        self.settings.sso_google_requires_2fa = True
        self.settings.save(update_fields=['sso_google_requires_2fa'])
        self.user.otp_secret = pyotp.random_base32()
        self.user.save(update_fields=['otp_secret'])
        response = self._response()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/verify-2fa/', response['Location'])

    def test_sso_pending_blocks_navigation_even_with_an_old_verified_session(self):
        self.settings.sso_google_requires_2fa = True
        self.settings.save(update_fields=['sso_google_requires_2fa'])
        self.user.otp_secret = pyotp.random_base32()
        self.user.save(update_fields=['otp_secret'])
        TenantMembership.objects.create(user=self.user, client=self.tenant, is_active=True)

        client = TenantClient(self.tenant)
        client.force_login(self.user)
        session = client.session
        session['is_2fa_verified'] = True
        session['twofa_verified_user_id'] = self.user.pk
        session['twofa_verified_client_id'] = self.tenant.pk
        session.save()

        token = build_sso_token(self.user.pk, self.tenant.schema_name, '/login/home/')
        response = client.get('/login/sso/consume/', {'token': token})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/sso/verify-2fa/', response['Location'])
        self.assertNotIn('_auth_user_id', client.session)
        self.assertNotIn('is_2fa_verified', client.session)

        blocked = client.get('/monitoring/')
        self.assertEqual(blocked.status_code, 302)
        self.assertIn('/login/sso/verify-2fa/', blocked['Location'])
        form = client.get('/login/sso/verify-2fa/')
        self.assertEqual(form.status_code, 200)
        self.assertNotContains(form, 'id="sidebar"')

        verified = client.post('/login/sso/verify-2fa/', {
            'code': pyotp.TOTP(self.user.otp_secret).now(),
        })
        self.assertEqual(verified.status_code, 302)
        self.assertEqual(verified['Location'], '/login/home/')
        self.assertEqual(client.get('/login/home/').status_code, 200)

    def test_required_policy_with_secret_routes_to_enrollment_until_confirmed(self):
        self.settings.multifactor_status = MultiFactorStatus.REQUIRED
        self.settings.save(update_fields=['multifactor_status'])
        self.user.otp_secret = 'JBSWY3DPEHPK3PXP'
        self.user.save(update_fields=['otp_secret'])
        self.assertIn('show-qr-code-2fa', self._response()['Location'])

    def test_enabling_2fa_from_profile_shows_png_qr(self):
        self.settings.multifactor_status = MultiFactorStatus.OPTIONAL
        self.settings.save(update_fields=['multifactor_status'])
        client = TenantClient(self.tenant)
        client.force_login(self.user)

        response = client.post('/login/profile/', {
            'first_name': 'MFA',
            'last_name': 'User',
            'email': self.user.email,
            'position': 'Analista',
            'menu_color': '#212629',
            'is_2fa_enabled': 'on',
            'language': 'es',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login/show-qr-code-2fa/')

        response = client.get(response['Location'])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'src="data:image/png;base64,')
        self.user.refresh_from_db()
        self.assertTrue(self.user.otp_secret)

    def test_disabled_policy_does_not_let_profile_enable_2fa(self):
        self.settings.multifactor_status = MultiFactorStatus.DISABLED
        self.settings.save(update_fields=['multifactor_status'])
        client = TenantClient(self.tenant)
        client.force_login(self.user)

        response = client.post('/login/profile/', {
            'first_name': 'MFA',
            'last_name': 'User',
            'email': self.user.email,
            'position': 'Analista',
            'menu_color': '#212629',
            'is_2fa_enabled': 'on',
            'language': 'es',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login/profile/')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_2fa_enabled)
        self.assertContains(client.get('/login/profile/'), 'Deshabilitada para este espacio')

    def test_optional_2fa_is_required_again_after_logout(self):
        import pyotp

        self.settings.multifactor_status = MultiFactorStatus.OPTIONAL
        self.settings.save(update_fields=['multifactor_status'])
        self.user.otp_secret = pyotp.random_base32()
        self.user.is_2fa_enabled = True
        self.user.save(update_fields=['otp_secret', 'is_2fa_enabled'])
        client = TenantClient(self.tenant)
        client.force_login(self.user)

        first_access = client.get('/login/home/')
        self.assertEqual(first_access.status_code, 302)
        self.assertIn('/login/verify-2fa/', first_access['Location'])
        verification = client.post('/login/verify-2fa/', {
            'otp_code': pyotp.TOTP(self.user.otp_secret).now(),
        })
        self.assertEqual(verification.status_code, 302)

        client.post('/login/logout/')
        client.force_login(self.user)
        next_access = client.get('/login/home/')
        self.assertEqual(next_access.status_code, 302)
        self.assertIn('/login/verify-2fa/', next_access['Location'])

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
