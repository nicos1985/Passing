from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("timezone/", views.set_display_timezone, name="timezone"),
    path("status/", views.status_page, name="status"),
    path("maintenance-windows/", views.maintenance_windows, name="maintenance_windows"),
    path("maintenance-windows/new/", views.maintenance_window_form, name="maintenance_window_new"),
    path("maintenance-windows/<int:pk>/edit/", views.maintenance_window_form, name="maintenance_window_edit"),
    path("maintenance-windows/<int:pk>/delete/", views.maintenance_window_delete, name="maintenance_window_delete"),
    path("", views.dashboard, name="dashboard"),
    path("live/", views.live_status, name="live"),
    path("history/", views.hourly_history, name="history"),
    path("information/", views.information, name="information"),
    path("groups/", views.monitor_group_list, name="groups"),
    path("groups/new/", views.monitor_group_form, name="group_new"),
    path("groups/<int:pk>/edit/", views.monitor_group_form, name="group_edit"),
    path("groups/<int:pk>/delete/", views.monitor_group_delete, name="group_delete"),
    path("new/", views.monitor_form, name="new"),
    path("<int:pk>/", views.monitor_detail, name="detail"),
    path("<int:pk>/data/", views.monitor_detail_data, name="detail_data"),
    path("<int:pk>/availability/", views.monitor_availability_data, name="availability"),
    path("<int:pk>/edit/", views.monitor_form, name="edit"),
    path("<int:pk>/heartbeat/", views.heartbeat_signal, name="heartbeat_signal"),
    path("<int:pk>/heartbeat/regenerate/", views.regenerate_heartbeat_token, name="heartbeat_regenerate"),
    path("<int:pk>/deployments/new/", views.deployment_form, name="deployment_new"),
    path("<int:pk>/deployments/<int:marker_pk>/edit/", views.deployment_form, name="deployment_edit"),
    path("<int:pk>/deployments/<int:marker_pk>/delete/", views.deployment_delete, name="deployment_delete"),
    path("<int:pk>/maintenance/", views.maintenance, name="maintenance"),
    path("<int:pk>/toggle/", views.toggle_active, name="toggle"),
    path("<int:pk>/delete/", views.delete_monitor, name="delete"),
    path("incidents/", views.incident_list, name="incidents"),
    path("incidents/<int:pk>/", views.incident_detail, name="incident"),
    path("incidents/<int:pk>/acknowledge/", views.acknowledge, name="acknowledge"),
    path("incidents/<int:pk>/test/<str:channel>/", views.test_notification_connection, name="test_notification"),
    path("incidents/<int:pk>/test-email/", views.test_email_delivery, name="test_email"),
    path("deliveries/<int:pk>/retry/", views.retry_delivery, name="retry_delivery"),
]
