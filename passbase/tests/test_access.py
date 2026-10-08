"""Regression checks for object authorization in the password vault."""

from django.http import Http404
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase
from cryptography.fernet import Fernet
from unittest.mock import patch

from accounts.models import CustomUser
from passbase.forms import ContrasenaForm
from passbase.models import Contrasena, LogData, SeccionContra
from passbase.views import ContrasCreateView, ContrasDeleteView, ContrasUpdateView, DescargarArchivo
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
