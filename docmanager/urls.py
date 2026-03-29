from django.urls import path

from .views import (
    DocumentInsightsView,
    drive_browser_view,
    drive_credential_view,
    drive_revisions_view,
    drive_status_view,
    drive_webhook_receiver,
)

app_name = "docmanager"

urlpatterns = [
    path("webhook/drive/", drive_webhook_receiver, name="drive_webhook"),
    path("config/drive/", drive_credential_view, name="drive_config"),
    path("config/drive/status/", drive_status_view, name="drive_status"),
    path("config/drive/browse/", drive_browser_view, name="drive_browse"),
    path("config/drive/revisions/", drive_revisions_view, name="drive_revisions"),
    path("insights/", DocumentInsightsView.as_view(), name="insights"),
]
