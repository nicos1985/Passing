"""Regression tests: previously exploitable requests must now be rejected."""
from io import StringIO
from unittest.mock import mock_open, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from notifications.models import AdminNotification
from passbase.models import Contrasena, SeccionContra
from permission.models import ContraPermission, PermissionRoles


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SecurityRegressionTests(TestCase):
    def setUp(self):
        # Silence application debug prints so audit output never includes secrets.
        output = patch('sys.stdout', new_callable=StringIO)
        self.output = output.start()
        self.addCleanup(output.stop)
        role = PermissionRoles.objects.create(pk=1, rol_name='Audit role')
        self.regular = get_user_model().objects.create_user(
            username='audit_member', email='audit_member@example.test',
            password='Audit-only-password-6842', assigned_role=role,
        )
        self.owner = get_user_model().objects.create_user(
            username='audit_owner', email='audit_owner@example.test',
            password='Audit-only-password-6843', assigned_role=role,
        )
        self.staff = get_user_model().objects.create_user(
            username='audit_staff', email='audit_staff@example.test',
            password='Audit-only-password-6844', assigned_role=role, is_staff=True,
        )
        self.section = SeccionContra.objects.create(nombre_seccion='Audit section')
        self.secret = Contrasena.objects.create(
            nombre_contra='Audit private credential', seccion=self.section,
            usuario='audit-service-user', contraseña='Audit-secret-ONLY-7291!',
            link='example.test', info='Private test record', owner=self.owner,
            is_personal=True,
        )
        self.secret.file.save('private.txt', ContentFile(b'AUDIT PRIVATE FILE'))
        self.client = self.verified_client(self.regular)

    def verified_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        device = TOTPDevice.objects.create(user=user, name='default')
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        return client

    def csrf(self, client):
        client.get(reverse('login'))
        return client.cookies['csrftoken'].value

    def test_01_invalid_post_reveals_another_users_plaintext_password(self):
        self.assertFalse(ContraPermission.objects.filter(user_id=self.regular).exists())
        url = reverse('updatepass', args=[self.secret.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        # A forged external Origin without a CSRF token is rejected before dispatch.
        response = self.client.post(url, {}, HTTP_ORIGIN='https://untrusted.example')
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url, {'csrfmiddlewaretoken': self.csrf(self.client)})
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Audit-secret-ONLY-7291!', status_code=404)

    def test_02_post_modifies_another_users_password_without_csrf(self):
        response = self.client.post(reverse('updatepass', args=[self.secret.pk]), {
            'nombre_contra': self.secret.nombre_contra, 'seccion': self.section.pk,
            'usuario': 'changed-by-audit', 'contraseña': 'Changed-by-audit-8194!',
            'actualizacion': 30, 'link': 'example.test', 'info': 'Changed by audit',
            'is_personal': 'on',
        })
        self.assertEqual(response.status_code, 403)
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.get_decrypted_password(), 'Audit-secret-ONLY-7291!')

    def test_03_download_without_object_permission(self):
        response = self.client.get(reverse('downloadfile', args=[self.secret.pk]))
        self.assertEqual(response.status_code, 404)

    def test_04_staff_can_promote_itself_to_superuser(self):
        client = self.verified_client(self.staff)
        response = client.post(reverse('updateuser', args=[self.staff.pk]), {
            'csrfmiddlewaretoken': self.csrf(client),
            'username': self.staff.username, 'email': self.staff.email,
            'first_name': 'Audit', 'last_name': 'Staff', 'documento': '12345678',
            'position': 'Staff', 'address': 'Test', 'tel_number': '1234567',
            'is_active': 'on', 'is_staff': 'on', 'is_superuser': 'on',
        })
        self.assertEqual(response.status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_superuser)

    def test_05_regular_user_can_overwrite_smtp_configuration(self):
        with patch('passing.views.open', mock_open(), create=True) as writer:
            response = self.client.post(reverse('update_email_config'), {
                'csrfmiddlewaretoken': self.csrf(self.client),
                'email_host': 'smtp.audit.invalid', 'email_port': '587',
                'email_host_user': 'audit@example.test', 'email_host_password': 'FAKE-SMTP-PASSWORD',
            })
            self.assertEqual(response.status_code, 403)
            writer.assert_not_called()
            self.assertNotIn('FAKE-SMTP-PASSWORD', self.output.getvalue())

    def test_06_inactive_permission_still_reveals_password(self):
        self.secret.is_personal = False
        self.secret.save()
        ContraPermission.objects.create(user_id=self.regular, contra_id=self.secret,
                                       permission=True, perm_active=False)
        response = self.client.get(reverse('listpass'))
        self.assertNotContains(response, 'Audit-secret-ONLY-7291!')
        response = self.client.get(reverse('detailpass', args=[self.secret.pk]))
        self.assertNotContains(response, 'Audit-secret-ONLY-7291!', status_code=404)

    def test_07_stored_markup_is_escaped_to_superadmin(self):
        marker = '<img src="audit-missing-image" onerror="void(0)">'
        self.secret.nombre_contra = marker
        self.secret.is_personal = False
        self.secret.save()
        self.staff.is_superuser = True
        self.staff.save()
        notification = AdminNotification.objects.create(
            id_contrasena=self.secret, id_user=self.owner.username,
            id_user_share=self.regular, type_notification='Audit', action='Audit', comment='Audit')
        client = self.verified_client(self.staff)
        url = reverse('grantperm', args=[self.secret.pk, self.regular.pk, notification.pk, self.owner.username])
        response = client.post(url, {'csrfmiddlewaretoken': self.csrf(client)}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, marker)
        self.assertContains(response, '&lt;img')

    def test_08_get_request_cannot_grant_permission(self):
        notification = AdminNotification.objects.create(
            id_contrasena=self.secret, id_user=self.owner.username,
            id_user_share=self.regular, type_notification='Audit', action='Audit', comment='Audit')
        self.staff.is_superuser = True
        self.staff.save()
        client = self.verified_client(self.staff)
        response = client.get(reverse('grantperm', args=[
            self.secret.pk, self.regular.pk, notification.pk, self.owner.username]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(ContraPermission.objects.filter(user_id=self.regular, contra_id=self.secret).exists())

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=None)
    def test_09_public_registration_creates_active_account(self, captcha):
        client = Client(enforce_csrf_checks=True)
        token = self.csrf(client)
        response = client.post(reverse('register'), {
            'csrfmiddlewaretoken': token, 'username': 'audit_public_signup',
            'email': 'signup@example.test', 'password1': 'Audit-signup-983762!',
            'password2': 'Audit-signup-983762!', 'g-recaptcha-response': 'test',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(username='audit_public_signup').exists())

    def test_10_unrelated_user_can_delete_credential_and_its_permissions(self):
        ContraPermission.objects.create(user_id=self.owner, contra_id=self.secret, permission=True)
        response = self.client.post(reverse('deletepass', args=[self.secret.pk]), {
            'csrfmiddlewaretoken': self.csrf(self.client),
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ContraPermission.objects.filter(contra_id=self.secret.pk).exists())
        self.assertTrue(Contrasena.objects.filter(pk=self.secret.pk, active=True).exists())

    def test_11_credential_creation_prints_plaintext_password(self):
        password = 'Audit-plaintext-log-46291!'
        response = self.client.post(reverse('createpass'), {
            'csrfmiddlewaretoken': self.csrf(self.client),
            'nombre_contra': 'New audit credential', 'seccion': self.section.pk,
            'usuario': 'new-audit-account', 'contraseña': password,
            'actualizacion': 30, 'link': 'example.test', 'info': 'Audit only',
            'is_personal': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(password, self.output.getvalue())

    def test_owner_can_read_edit_download_and_soft_delete(self):
        client = self.verified_client(self.owner)
        self.assertContains(client.get(reverse('detailpass', args=[self.secret.pk])), 'Audit-secret-ONLY-7291!')
        response = client.get(reverse('downloadfile', args=[self.secret.pk]))
        self.assertEqual(b''.join(response.streaming_content), b'AUDIT PRIVATE FILE')
        self.assertIn('attachment', response['Content-Disposition'])
        response = client.post(reverse('updatepass', args=[self.secret.pk]), {
            'csrfmiddlewaretoken': self.csrf(client), 'nombre_contra': self.secret.nombre_contra,
            'seccion': self.section.pk, 'link': 'example.test', 'usuario': 'edited-user',
            'contraseña': 'Edited-owner-secret-7562!', 'actualizacion': 30, 'info': 'edited', 'is_personal': 'on',
            'owner': self.regular.pk, 'active': '',
        })
        self.assertEqual(response.status_code, 302)
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.owner, self.owner)
        self.assertTrue(self.secret.active)
        self.assertEqual(self.secret.get_decrypted_password(), 'Edited-owner-secret-7562!')
        ContraPermission.objects.create(user_id=self.owner, contra_id=self.secret, permission=True)
        response = client.post(reverse('deletepass', args=[self.secret.pk]), {'csrfmiddlewaretoken': self.csrf(client)})
        self.assertEqual(response.status_code, 302)
        self.secret.refresh_from_db()
        self.assertFalse(self.secret.active)
        self.assertTrue(ContraPermission.objects.filter(contra_id=self.secret).exists())

    def test_shared_access_is_revoked_immediately(self):
        self.secret.is_personal = False
        self.secret.save()
        permission = ContraPermission.objects.create(user_id=self.regular, contra_id=self.secret, permission=True, perm_active=True)
        self.assertContains(self.client.get(reverse('detailpass', args=[self.secret.pk])), 'Audit-secret-ONLY-7291!')
        self.assertEqual(self.client.get(reverse('updatepass', args=[self.secret.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('deletepass', args=[self.secret.pk])).status_code, 404)
        permission.perm_active = False
        permission.save()
        for name in ('detailpass', 'updatepass', 'downloadfile'):
            self.assertEqual(self.client.get(reverse(name, args=[self.secret.pk])).status_code, 404)

    def test_personal_credentials_ignore_sharing_rows_even_for_superadmin(self):
        self.staff.is_superuser = True
        self.staff.save()
        client = self.verified_client(self.staff)
        ContraPermission.objects.create(user_id=self.staff, contra_id=self.secret, permission=True, perm_active=True)
        self.assertEqual(client.get(reverse('detailpass', args=[self.secret.pk])).status_code, 404)
        self.assertNotContains(client.get(reverse('listpass')), 'Audit-secret-ONLY-7291!')

    def test_staff_cannot_manage_administration(self):
        client = self.verified_client(self.staff)
        for name in ('userlist', 'register', 'config', 'permissionlist', 'permissionform1', 'roles', 'assignroluser', 'listsection'):
            with self.subTest(view=name):
                self.assertEqual(client.get(reverse(name)).status_code, 403)
        self.assertEqual(client.get('/admin/').status_code, 403)

    def test_authenticated_superadmin_without_otp_cannot_register_accounts(self):
        self.staff.is_superuser = True
        self.staff.save()
        client = Client()
        client.force_login(self.staff)
        self.assertEqual(client.get(reverse('register')).status_code, 302)

    def test_superadmin_can_grant_and_revoke_via_permission_form(self):
        self.staff.is_superuser = True
        self.staff.save()
        self.secret.is_personal = False
        self.secret.save()
        client = self.verified_client(self.staff)
        url = reverse('permissionform2', args=[self.regular.pk])
        response = client.post(url, {'csrfmiddlewaretoken': self.csrf(client), f'permiso_{self.secret.pk}': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse('detailpass', args=[self.secret.pk])).status_code, 200)
        response = client.post(url, {'csrfmiddlewaretoken': self.csrf(client)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse('detailpass', args=[self.secret.pk])).status_code, 404)

    def test_secret_responses_are_not_cached(self):
        client = self.verified_client(self.owner)
        for name in ('detailpass', 'downloadfile'):
            response = client.get(reverse(name, args=[self.secret.pk]))
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            response.close()

    def test_profile_email_change_requires_password_and_rejects_css(self):
        from login.forms import ProfileForm
        data = {'email': 'new@example.test', 'menu_color': '#abcdef', 'position': 'Tester'}
        form = ProfileForm(data, instance=self.regular)
        self.assertFalse(form.is_valid())
        self.assertIn('current_password', form.errors)
        self.regular.refresh_from_db()
        form = ProfileForm({**data, 'current_password': 'Audit-only-password-6842'}, instance=self.regular)
        self.assertTrue(form.is_valid(), form.errors)
        self.regular.refresh_from_db()
        form = ProfileForm({'email': self.regular.email, 'menu_color': 'red;/*'}, instance=self.regular)
        self.assertFalse(form.is_valid())

    def test_reject_active_uploads_and_oversized_requests(self):
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from passing.uploads import validate_attachment
        with self.assertRaises(ValidationError):
            validate_attachment(SimpleUploadedFile('payload.html', b'<script>alert(1)</script>'))
        self.assertEqual(self.client.post(reverse('createpass'), {}, CONTENT_LENGTH=str(13 * 1024 * 1024)).status_code, 413)

    def test_password_reset_rate_limit_is_shared_between_clients(self):
        first, second = Client(enforce_csrf_checks=True), Client(enforce_csrf_checks=True)
        for i in range(11):
            client = first if i % 2 else second
            response = client.post(reverse('password_reset'), {
                'csrfmiddlewaretoken': self.csrf(client), 'email': 'nonexistent@example.test'})
            self.assertEqual(response.status_code, 302 if i < 10 else 429)

    def test_key_rotation_dry_run_and_atomic_apply_preserve_plaintext(self):
        import os
        from cryptography.fernet import Fernet
        from django.core.management import call_command
        from passbase.views import audit_credential
        from passbase.models import LogData
        audit_credential(self.owner, self.secret, 'Create')
        old_ciphertext = Contrasena.objects.get(pk=self.secret.pk).contraseña
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {'PASSING_NEW_CRYPTOGRAPHY_KEY': key}):
            call_command('rotate_vault_key', stdout=StringIO())
            self.assertEqual(Contrasena.objects.get(pk=self.secret.pk).contraseña, old_ciphertext)
            call_command('rotate_vault_key', apply=True, backup_confirmed=True, stdout=StringIO())
        with override_settings(CRYPTOGRAPHY_KEY=key):
            self.secret.refresh_from_db()
            self.assertEqual(self.secret.get_decrypted_password(), 'Audit-secret-ONLY-7291!')
            self.assertEqual(LogData.objects.get().get_decrypted_password(), 'Audit-secret-ONLY-7291!')

    def test_invalid_ciphertext_fails_closed(self):
        from passbase.crypto import decrypt_data, encrypt_data
        with self.assertRaises(ValueError):
            decrypt_data('unexpected plaintext')
        self.assertEqual(decrypt_data(encrypt_data("b'legitimate-password'")), "b'legitimate-password'")

    def test_submitted_ciphertext_is_stored_as_literal_password(self):
        from passbase.forms import ContrasenaForm
        submitted = str(self.secret.contraseña)
        form = ContrasenaForm({'nombre_contra': 'Literal token', 'seccion': self.section.pk,
                              'usuario': 'literal-user', 'contraseña': submitted,
                              'link': 'example.test', 'info': 'test', 'actualizacion': 30})
        self.assertTrue(form.is_valid(), form.errors)
        credential = form.save(commit=False)
        credential.owner = self.regular
        credential.save()
        credential.refresh_from_db()
        self.assertEqual(credential.get_decrypted_password(), submitted)

    def test_failed_rotation_rolls_back_records_already_processed(self):
        import os
        from cryptography.fernet import Fernet
        from django.core.management import call_command, CommandError
        damaged = Contrasena.objects.create(nombre_contra='Damaged', seccion=self.section,
                                             usuario='test', contraseña='test', owner=self.owner)
        Contrasena.objects.filter(pk=damaged.pk).update(contraseña='invalid ciphertext')
        original = Contrasena.objects.get(pk=self.secret.pk).contraseña
        with patch.dict(os.environ, {'PASSING_NEW_CRYPTOGRAPHY_KEY': Fernet.generate_key().decode()}):
            with self.assertRaises(CommandError):
                call_command('rotate_vault_key', apply=True, backup_confirmed=True, stdout=StringIO())
        self.assertEqual(Contrasena.objects.get(pk=self.secret.pk).contraseña, original)

    def test_superadmin_cannot_deactivate_self_through_departure_form(self):
        self.staff.is_superuser = True
        self.staff.save()
        client = self.verified_client(self.staff)
        response = client.post(reverse('deactivateuser', args=[self.staff.pk]), {
            'csrfmiddlewaretoken': self.csrf(client), 'departure_date': '2026-09-17',
            'departure_motive': 'test', 'is_active': '',
        })
        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_untrusted_forwarded_ip_does_not_bypass_login_limits(self):
        from django.test import RequestFactory
        from types import SimpleNamespace
        from securitycontrol.middleware import SecurityMiddleware
        middleware = SecurityMiddleware(lambda request: None)
        for i in range(11):
            request = RequestFactory().post('/login/reset-password/', {'email': f'user{i}@example.test'},
                                            REMOTE_ADDR='192.0.2.1', HTTP_X_REAL_IP=f'198.51.100.{i}')
            request.resolver_match = SimpleNamespace(view_name='password_reset')
            response = middleware.process_view(request, None, (), {})
            if i < 10:
                self.assertIsNone(response)
            else:
                self.assertEqual(response.status_code, 429)
