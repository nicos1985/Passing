"""Entrypoints deshabilitados mientras Passing usa un solo tenant sin Drive."""

from unittest.mock import patch

from django.contrib import admin
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import Resolver404, resolve

from client.views import client_register as legacy_client_register
from docmanager.models import DocumentoControlado, IntegrationCredential
from docmanager.services import GoogleDriveService, GoogleDriveServiceError
from docmanager.tasks import process_drive_change
from passing.views import client_register


class DisabledFeaturesTests(SimpleTestCase):
    def test_registration_rejects_get_and_post(self):
        factory = RequestFactory()
        for view in (client_register, legacy_client_register):
            for request in (factory.get("/client-register/"), factory.post("/client-register/")):
                with self.assertRaises(Http404):
                    view(request)

    def test_drive_routes_are_not_exposed(self):
        for path in ("/docmanager/webhook/drive/", "/docmanager/config/drive/"):
            with self.assertRaises(Resolver404):
                resolve(path, urlconf="passing.urls_tenant")

    def test_drive_service_and_task_cannot_connect(self):
        with self.assertRaises(GoogleDriveServiceError):
            GoogleDriveService(None)
        with patch("docmanager.tasks.DocumentoControlado.objects.get") as lookup:
            self.assertEqual(process_drive_change("unused"), "drive_deshabilitado")
            lookup.assert_not_called()

    def test_drive_models_are_not_in_admin(self):
        self.assertFalse(admin.site.is_registered(IntegrationCredential))
        self.assertFalse(admin.site.is_registered(DocumentoControlado))
