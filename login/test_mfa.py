import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY, verify_token
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from permission.models import PermissionRoles


class MandatoryMFATests(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = PermissionRoles.objects.create(rol_name='Test')
        cls.user = get_user_model().objects.create_user(
            username='member', email='member@example.com', password='test-password',
            assigned_role=role,
        )
        cls.admin_user = get_user_model().objects.create_superuser(
            username='administrator', email='admin@example.com', password='admin-password',
            assigned_role=role,
        )

    def device(self, user=None):
        return TOTPDevice.objects.create(user=user or self.user, name='default')

    def verified_client(self, user, device):
        client = Client()
        client.force_login(user)
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        return client

    def test_anonymous_cannot_access_application_or_admin(self):
        for path in ('/pass/listpass', '/admin/', '/test_send_email/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('two_factor:login'), response.url)

    def test_existing_session_without_device_must_enroll(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('listpass')), reverse('two_factor:setup'),
                             fetch_redirect_response=False)
        response = self.client.get(reverse('two_factor:setup'))
        self.assertContains(response, 'Configurar segundo factor')
        self.assertIn('no-store', response['Cache-Control'])

    def test_password_only_session_with_device_cannot_access_or_replace_qr(self):
        self.device()
        self.client.force_login(self.user)
        for name in ('listpass', 'two_factor:setup', 'two_factor:qr'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('two_factor:login'), response.url)
        response = self.client.post(reverse('two_factor:setup'), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)

    def test_verified_user_can_access_security_but_no_disable_or_backup_routes(self):
        client = self.verified_client(self.user, self.device())
        self.assertContains(client.get(reverse('two_factor:profile')), 'Segundo factor activado')
        for path in ('/security/disable/', '/security/backup/tokens/'):
            self.assertEqual(client.get(path).status_code, 404)
        self.assertFalse(admin.site.is_registered(TOTPDevice))

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=None)
    def test_login_requires_password_then_totp_and_rejects_replay(self, captcha):
        device = self.device()
        response = self.client.get(reverse('login'))
        wizard = response.context['wizard']['management_form'].prefix
        response = self.client.post(reverse('login'), {
            f'{wizard}-current_step': 'auth', 'auth-username': self.user.username,
            'auth-password': 'test-password', 'g-recaptcha-response': 'test',
        })
        self.assertEqual(response.context['wizard']['steps'].current, 'token')
        self.assertNotIn('_auth_user_id', self.client.session)
        token = str(totp(device.bin_key)).zfill(6)
        response = self.client.post(reverse('login'), {
            f'{wizard}-current_step': 'token', 'token-otp_token': token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(DEVICE_ID_SESSION_KEY, self.client.session)
        self.assertIsNone(verify_token(self.user, device.persistent_id, token))

    def test_enrollment_requires_valid_code_and_consumes_it(self):
        self.client.force_login(self.user)
        url = reverse('two_factor:setup')
        response = self.client.get(url)
        wizard = response.context['wizard']['management_form'].prefix
        response = self.client.post(url, {f'{wizard}-current_step': 'welcome'})
        self.assertEqual(response.context['wizard']['steps'].current, 'generator')
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.get(reverse('two_factor:qr')).status_code, 200)
        key = response.context['wizard']['form'].bin_key
        token = str(totp(key)).zfill(6)
        response = self.client.post(url, {
            f'{wizard}-current_step': 'generator', 'generator-token': token,
        })
        self.assertEqual(response.status_code, 302)
        device = TOTPDevice.objects.get(user=self.user)
        self.assertIn(DEVICE_ID_SESSION_KEY, self.client.session)
        self.assertIsNone(verify_token(self.user, device.persistent_id, token))

    def test_recovery_requires_superadmin_and_fresh_verification(self):
        target_device = self.device()
        admin_device = self.device(self.admin_user)
        victim_client = self.verified_client(self.user, target_device)
        victim_session = victim_client.session.session_key
        client = self.verified_client(self.admin_user, admin_device)
        url = reverse('two_factor:recover', args=[self.user.pk])
        self.assertEqual(victim_client.get(url).status_code, 403)
        self.assertEqual(client.get(reverse('two_factor:recover', args=[self.admin_user.pk])).status_code, 403)
        self.assertEqual(client.get(url).status_code, 200)
        self.assertTrue(TOTPDevice.objects.filter(pk=target_device.pk).exists())
        response = client.post(url, {'password': 'incorrect',
                                     'token': str(totp(admin_device.bin_key)).zfill(6)})
        self.assertContains(response, 'Verificación incorrecta')
        self.assertTrue(TOTPDevice.objects.filter(pk=target_device.pk).exists())
        # A newly generated code is required after the failed password check.
        admin_device.refresh_from_db()
        token = str(totp(admin_device.bin_key, drift=1)).zfill(6)
        response = client.post(url, {'password': 'admin-password', 'token': token})
        self.assertContains(response, 'Se invalidaron')
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(Session.objects.filter(session_key=victim_session).exists())
        self.assertTrue(TOTPDevice.objects.filter(user=self.admin_user).exists())

    def test_password_reset_preserves_totp_device(self):
        device = self.device()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.get(reverse('password_reset_confirm', args=[uid, token]))
        response = self.client.post(response.url, {
            'new_password1': 'New-strong-password-8194',
            'new_password2': 'New-strong-password-8194',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TOTPDevice.objects.filter(pk=device.pk).exists())
        self.assertNotIn(DEVICE_ID_SESSION_KEY, self.client.session)

    def test_incorrect_token_is_throttled_and_expired_token_rejected(self):
        device = self.device()
        with patch('django_otp.plugins.otp_totp.models.time.time', return_value=time.time()):
            self.assertIsNone(verify_token(self.user, device.persistent_id, 'not-a-code'))
            device.refresh_from_db()
            self.assertFalse(device.verify_is_allowed()[0])
            self.assertIsNone(verify_token(self.user, device.persistent_id,
                                           str(totp(device.bin_key)).zfill(6)))
            device.throttle_reset()
            expired = str(totp(device.bin_key, drift=-10)).zfill(6)
            self.assertIsNone(verify_token(self.user, device.persistent_id, expired))

    def test_recovery_rejects_post_without_csrf(self):
        device = self.device(self.admin_user)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        response = client.post(reverse('two_factor:recover', args=[self.user.pk]), {
            'password': 'admin-password', 'token': str(totp(device.bin_key)).zfill(6),
        })
        self.assertEqual(response.status_code, 403)

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=None)
    def test_browser_login_preserves_origin_and_enforces_csrf(self, captcha):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse('login'))
        self.assertContains(response, 'name="referrer" content="same-origin"')
        wizard = response.context['wizard']['management_form'].prefix
        data = {
            f'{wizard}-current_step': 'auth', 'auth-username': self.user.username,
            'auth-password': 'test-password', 'g-recaptcha-response': 'test',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }
        self.assertEqual(client.post(reverse('login'), data, HTTP_ORIGIN='null').status_code, 403)
        self.assertEqual(client.post(reverse('login'), data,
                                      HTTP_ORIGIN='http://other.example').status_code, 403)
        response = client.post(reverse('login'), data, HTTP_ORIGIN='http://testserver')
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', client.session)

    def test_session_expires_after_24_hours_even_with_activity(self):
        started = timezone.now()
        deadline = started + timedelta(hours=24)
        device = self.device()
        with patch('django.utils.timezone.now', return_value=started):
            client = self.verified_client(self.user, device)
        session_key = client.session.session_key
        self.assertEqual(Session.objects.get(session_key=session_key).expire_date, deadline)

        # Even writes such as messages or preferences must retain the original deadline.
        with patch('django.utils.timezone.now', return_value=started + timedelta(hours=12)):
            session = client.session
            session['test_preference'] = 'updated'
            session.save()
            self.assertEqual(client.get(reverse('two_factor:profile')).status_code, 200)
            self.assertEqual(Session.objects.get(session_key=session_key).expire_date, deadline)

        with patch('django.utils.timezone.now', return_value=deadline - timedelta(seconds=1)):
            self.assertEqual(client.get(reverse('two_factor:profile')).status_code, 200)
        with patch('django.utils.timezone.now', return_value=deadline):
            response = client.get(reverse('two_factor:profile'))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('two_factor:login'), response.url)
            self.assertNotIn('_auth_user_id', client.session)
            self.assertNotIn(DEVICE_ID_SESSION_KEY, client.session)

    def test_logout_ends_session_before_daily_deadline(self):
        client = self.verified_client(self.user, self.device())
        client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', client.session)
        response = client.get(reverse('two_factor:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('two_factor:login'), response.url)
