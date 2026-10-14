"""Regression checks for object authorization in the password vault."""

import json
from django.http import Http404
from django.test import RequestFactory, override_settings
from django_tenants.test.cases import TenantTestCase
from cryptography.fernet import Fernet
from unittest.mock import patch

from accounts.models import CustomUser
from passbase.forms import ContrasenaForm
from passbase.models import Contrasena, LogData, SeccionContra
from passbase.views import ContrasCreateView, ContrasDeleteView, ContrasDetailView, ContrasUpdateView, ContrasListView, SectionDeleteView, reveal_credential, DescargarArchivo
from permission.models import ContraPermission
from passing import settings as project_settings


class VaultAccessTests(TenantTestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create(username="vault-owner", email="owner@example.test", client=self.tenant)
        self.other = CustomUser.objects.create(username="vault-other", email="other@example.test", client=self.tenant)
        section = SeccionContra.objects.create(nombre_seccion="Interna")
        # bulk_create avoids invoking encryption; these tests only exercise authorization.
        self.password = Contrasena.objects.bulk_create([
            Contrasena(nombre_contra="Acceso sensible", seccion=section, link="https://example.test",
                       usuario="encrypted-user", contraseña="encrypted-password", owner=self.owner),
        ])[0]
        ContraPermission.objects.create(user_id=self.owner, contra_id=self.password, permission="True", perm_active=True)
        self.factory = RequestFactory()

    def _request(self, method, path, user):
        request = getattr(self.factory, method)(path)
        request.user = user
        return request

    def test_update_post_cannot_reach_another_users_password(self):
        request = self._request("post", "/pass/editpass/1", self.other)
        with self.assertRaises(Http404):
            ContrasUpdateView.as_view()(request, pk=self.password.pk)

    @override_settings(ROOT_URLCONF='passing.urls_tenant')
    def test_list_does_not_decrypt_credentials(self):
        request = self._request('get', '/pass/listpass', self.owner)
        with patch.object(Contrasena, 'get_decrypted_password', side_effect=AssertionError('eager decrypt')):
            response = ContrasListView.as_view()(request)
            response.render()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'encrypted-password', response.content)

    def test_reveal_requires_active_permission_and_post(self):
        with patch.object(project_settings, 'CRYPTOGRAPHY_KEY', Fernet.generate_key()):
            entry = Contrasena.objects.create(
                nombre_contra='Revelación puntual', seccion=self.password.seccion,
                link='https://example.test', usuario='alice', contraseña='secret-value',
                info='prueba', owner=self.owner,
            )
            permission = ContraPermission.objects.create(
                user_id=self.owner, contra_id=entry, permission=True, perm_active=True,
            )
            denied_request = self.factory.post('/pass/revealpass/1', {'field': 'password'})
            denied_request.user = self.other
            with self.assertRaises(Http404):
                reveal_credential(denied_request, entry.pk)
            request = self.factory.post('/pass/revealpass/1', {'field': 'password'})
            request.user = self.owner
            response = reveal_credential(request, entry.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content), {'value': 'secret-value'})
            self.assertIn('no-store', response['Cache-Control'])
            username_request = self.factory.post('/pass/revealpass/1', {'field': 'username'})
            username_request.user = self.owner
            self.assertEqual(json.loads(reveal_credential(username_request, entry.pk).content), {'value': 'alice'})
            self.assertEqual(reveal_credential(self._request('get', '/pass/revealpass/1', self.owner), entry.pk).status_code, 405)
            permission.perm_active = False
            permission.save(update_fields=['perm_active'])
            with self.assertRaises(Http404):
                reveal_credential(request, entry.pk)

    @override_settings(ROOT_URLCONF='passing.urls_tenant')
    def test_detail_does_not_embed_plaintext_secret(self):
        with patch.object(project_settings, 'CRYPTOGRAPHY_KEY', Fernet.generate_key()):
            entry = Contrasena.objects.create(
                nombre_contra='Detalle privado', seccion=self.password.seccion,
                link='https://example.test', usuario='private-user', contraseña='private-secret',
                info='prueba', owner=self.owner,
            )
            ContraPermission.objects.create(user_id=self.owner, contra_id=entry, permission=True, perm_active=True)
            response = ContrasDetailView.as_view()(
                self._request('get', f'/pass/detailpass/{entry.pk}', self.owner), pk=entry.pk,
            )
            response.render()
            self.assertNotIn(b'private-secret', response.content)
            self.assertNotIn(b'private-user', response.content)

    @override_settings(ROOT_URLCONF='passing.urls_tenant')
    def test_deactivating_section_preserves_credentials(self):
        request = self._request('post', f'/pass/deletesection/{self.password.seccion_id}', self.owner)
        response = SectionDeleteView.as_view()(request, pk=self.password.seccion_id)
        self.assertEqual(response.status_code, 302)
        self.password.seccion.refresh_from_db()
        self.assertFalse(self.password.seccion.active)
        self.assertTrue(Contrasena.objects.filter(pk=self.password.pk).exists())

    def test_update_requires_csrf(self):
        self.assertFalse(getattr(ContrasUpdateView.as_view(), "csrf_exempt", False))

    def test_attachment_requires_permission(self):
        request = self._request("get", "/pass/downloadfile/1", self.other)
        with self.assertRaises(Http404):
            DescargarArchivo.as_view()(request, pk=self.password.pk)

    def test_only_owner_can_deactivate_password(self):
        request = self._request("post", "/pass/deletepass/1", self.other)
        with self.assertRaises(Http404):
            ContrasDeleteView.as_view()(request, pk=self.password.pk)
        self.password.refresh_from_db()
        self.assertTrue(self.password.active)

        owner_request = self._request("post", "/pass/deletepass/1", self.owner)
        response = ContrasDeleteView.as_view(success_url="/pass/listpass")(owner_request, pk=self.password.pk)
        self.assertEqual(response.status_code, 302)
        self.password.refresh_from_db()
        self.assertFalse(self.password.active)
        self.assertEqual(LogData.objects.filter(contraseña=self.password.pk, action="Inactive").get().password,
                         "[REDACTED]")

    def test_create_encrypts_credentials_once(self):
        form = ContrasenaForm(data={
            "nombre_contra": "Nuevo acceso", "seccion": self.password.seccion_id,
            "link": "https://example.test", "usuario": "alice",
            "contraseña": "example-secret", "actualizacion": 30,
            "info": "Cuenta de prueba", "is_personal": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        request = self._request("post", "/pass/createpass", self.owner)
        view = ContrasCreateView()
        view.request = request
        view.success_url = "/pass/listpass"
        with patch.object(project_settings, "CRYPTOGRAPHY_KEY", Fernet.generate_key()):
            response = view.form_valid(form)
            saved = Contrasena.objects.get(nombre_contra="Nuevo acceso")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(saved.get_decrypted_user(), "alice")
            self.assertEqual(saved.get_decrypted_password(), "example-secret")

    def test_metadata_save_preserves_existing_ciphertext(self):
        with patch.object(project_settings, "CRYPTOGRAPHY_KEY", Fernet.generate_key()):
            entry = Contrasena.objects.create(
                nombre_contra='Cifrado estable', seccion=self.password.seccion,
                link='https://example.test', usuario='alice', contraseña='secreto',
                info='inicio', owner=self.owner,
            )
            original_user, original_password = entry.usuario, entry.contraseña
            entry.info = 'actualizado'
            entry.save(update_fields=['info'])
            entry.refresh_from_db()
            self.assertEqual((entry.usuario, entry.contraseña), (original_user, original_password))
            self.assertEqual(entry.get_decrypted_password(), 'secreto')
            entry.contraseña = 'nuevo secreto'
            entry.save()
            entry.refresh_from_db()
            self.assertEqual(entry.usuario, original_user)
            self.assertEqual(entry.get_decrypted_password(), 'nuevo secreto')
            self.assertEqual(LogData.objects.filter(contraseña=entry.pk).count(), 1)

    def test_opening_edit_form_does_not_write_secret_to_log(self):
        with patch.object(project_settings, "CRYPTOGRAPHY_KEY", Fernet.generate_key()):
            entry = Contrasena.objects.create(
                nombre_contra='Solo lectura', seccion=self.password.seccion,
                link='https://example.test', usuario='alice', contraseña='secreto',
                info='inicio', owner=self.owner,
            )
            ContraPermission.objects.create(user_id=self.owner, contra_id=entry, permission=True, perm_active=True)
            count = LogData.objects.filter(contraseña=entry.pk).count()
            response = ContrasUpdateView.as_view()(self._request('get', f'/pass/editpass/{entry.pk}', self.owner), pk=entry.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(LogData.objects.filter(contraseña=entry.pk).count(), count)

    def test_edit_credential_logs_only_change_type(self):
        with patch.object(project_settings, 'CRYPTOGRAPHY_KEY', Fernet.generate_key()):
            entry = Contrasena.objects.create(
                nombre_contra='Edición segura', seccion=self.password.seccion,
                link='https://example.test', usuario='alice', contraseña='original',
                info='inicio', owner=self.owner,
            )
            ContraPermission.objects.create(user_id=self.owner, contra_id=entry, permission=True, perm_active=True)
            data = {
                'nombre_contra': entry.nombre_contra, 'seccion': entry.seccion_id,
                'link': entry.link, 'usuario': 'alice', 'contraseña': 'cambiada',
                'actualizacion': entry.actualizacion, 'info': 'inicio',
                'is_personal': False,
            }
            request = self.factory.post(f'/pass/editpass/{entry.pk}', data)
            request.user = self.owner
            response = ContrasUpdateView.as_view(success_url='/pass/listpass')(request, pk=entry.pk)
            self.assertEqual(response.status_code, 302)
            entry.refresh_from_db()
            self.assertEqual(entry.get_decrypted_password(), 'cambiada')
            log = LogData.objects.filter(contraseña=entry.pk, action='change pass').get()
            self.assertEqual(log.password, '[REDACTED]')
            self.assertNotIn('cambiada', log.detail)
