"""Private document summaries must not be exposed to other users."""

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import DocumentInsightsView, drive_webhook_receiver


class DocumentInsightsAccessTests(SimpleTestCase):
    def test_non_staff_user_is_denied(self):
        request = RequestFactory().get("/docmanager/insights/")
        request.user = SimpleNamespace(is_authenticated=True, is_staff=False, is_superuser=False)
        with self.assertRaises(PermissionDenied):
            DocumentInsightsView.as_view()(request)

    @override_settings(DOCMANAGER_WEBHOOK_TOKEN="secret-channel-token")
    @patch("docmanager.views.process_drive_change.delay")
    def test_drive_webhook_rejects_wrong_token(self, delay):
        request = RequestFactory().post("/docmanager/webhook/drive/", HTTP_X_GOOG_RESOURCE_ID="file-id",
                                        HTTP_X_GOOG_CHANNEL_TOKEN="wrong-token")
        self.assertEqual(drive_webhook_receiver(request).status_code, 403)
        delay.assert_not_called()

    @override_settings(DOCMANAGER_WEBHOOK_TOKEN="secret-channel-token")
    @patch("docmanager.views.process_drive_change.delay")
    def test_drive_webhook_accepts_matching_token(self, delay):
        request = RequestFactory().post("/docmanager/webhook/drive/", HTTP_X_GOOG_RESOURCE_ID="file-id",
                                        HTTP_X_GOOG_CHANNEL_TOKEN="secret-channel-token")
        self.assertEqual(drive_webhook_receiver(request).status_code, 204)
        delay.assert_called_once()
