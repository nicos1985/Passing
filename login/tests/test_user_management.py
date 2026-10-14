"""La gestión de usuarios debe respetar el tenant y confirmar las altas reales."""

from unittest.mock import patch
from smtplib import SMTPConnectError

from django.test import override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser, TenantMembership


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class UserManagementTests(TenantTestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='admin_users', email='admin_users@example.test',
            password='test-password', client=self.tenant,
        )
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.admin)

    def test_list_and_edit_include_legacy_user_without_membership(self):
        legacy = CustomUser.objects.create_user(
            username='legacy_user', email='legacy@example.test',
            password='test-password', client=self.tenant,
        )
        self.assertFalse(TenantMembership.objects.filter(user=legacy).exists())
        response = self.client.get('/login/users/')
        self.assertContains(response, 'legacy_user')
        self.assertEqual(self.client.get(f'/login/update-user/{legacy.pk}').status_code, 200)
        response = self.client.post(f'/login/update-user/{legacy.pk}', {
            'username': 'legacy_user', 'email': 'legacy@example.test',
            'first_name': 'Editado',
        })
        self.assertEqual(response.status_code, 302)
        legacy.refresh_from_db()
        self.assertEqual(legacy.first_name, 'Editado')

    def test_user_outside_current_tenant_cannot_be_edited(self):
        outsider = CustomUser.objects.create_user(
            username='outsider', email='outsider@example.test', password='test-password',
        )
        response = self.client.get(f'/login/update-user/{outsider.pk}')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TenantMembership.objects.filter(user=outsider, client=self.tenant).exists())

    def test_revoked_membership_overrides_legacy_client_link(self):
        revoked = CustomUser.objects.create_user(
            username='revoked_user', email='revoked@example.test',
            password='test-password', client=self.tenant,
        )
        TenantMembership.objects.create(user=revoked, client=self.tenant, is_active=False)
        self.assertNotContains(self.client.get('/login/users/'), 'revoked_user')
        self.assertEqual(self.client.get(f'/login/update-user/{revoked.pk}').status_code, 302)

    def test_create_assigns_current_tenant_and_membership(self):
        response = self.client.post('/login/register/', {
            'username': 'nuevo_user', 'email': 'nuevo@example.test',
            'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 302)
        user = CustomUser.objects.get(username='nuevo_user')
        self.assertEqual(user.client_id, self.tenant.pk)
        self.assertTrue(TenantMembership.objects.filter(user=user, client=self.tenant, is_active=True).exists())
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertContains(self.client.get('/login/users/'), 'nuevo_user')

    def test_failed_save_does_not_claim_user_was_created(self):
        with patch('login.views.TenantMembership.objects.create', side_effect=RuntimeError('test failure')):
            response = self.client.post('/login/register/', {
                'username': 'failed_user', 'email': 'failed@example.test',
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se pudo crear el usuario')
        self.assertFalse(CustomUser.objects.filter(username='failed_user').exists())

    def test_legacy_pending_user_can_receive_new_invitation(self):
        pending = CustomUser.objects.create(
            username='pending_user', email='pending@example.test',
            client=self.tenant, is_active=False, password='',
        )
        with patch('login.views._send_activation_email') as send:
            response = self.client.post(f'/login/resend-activation/{pending.pk}/')
        self.assertEqual(response.status_code, 302)
        send.assert_called_once()
        self.assertContains(self.client.get('/login/users/'), 'Pendiente de activación')

    def test_resend_reports_smtp_connection_failure(self):
        pending = CustomUser.objects.create(
            username='pending_smtp', email='pending_smtp@example.test',
            client=self.tenant, is_active=False, password='',
        )
        with patch('login.views.send_mail', side_effect=SMTPConnectError(421, b'connection failed')):
            response = self.client.post(f'/login/resend-activation/{pending.pk}/', follow=True)
        self.assertContains(response, 'No se pudo conectar al servidor SMTP')
        self.assertNotContains(response, 'El servidor de correo aceptó la invitación')

    def test_resend_does_not_claim_success_when_backend_accepts_zero_messages(self):
        pending = CustomUser.objects.create(
            username='pending_zero', email='pending_zero@example.test',
            client=self.tenant, is_active=False, password='',
        )
        with patch('login.views.send_mail', return_value=0):
            response = self.client.post(f'/login/resend-activation/{pending.pk}/', follow=True)
        self.assertContains(response, 'El servidor de correo no aceptó la invitación')

    def test_staff_cannot_grant_admin_privileges_or_edit_superuser(self):
        staff = CustomUser.objects.create_user(
            username='staff_user', email='staff@example.test', password='test-password',
            client=self.tenant, is_staff=True,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(f'/login/update-user/{self.admin.pk}').status_code, 302)
        response = self.client.post('/login/register/', {
            'username': 'ordinary_user', 'email': 'ordinary@example.test',
            'is_staff': 'on', 'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 302)
        created = CustomUser.objects.get(username='ordinary_user')
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
