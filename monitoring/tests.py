from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone as dt_timezone
from contextlib import nullcontext
import json
import smtplib

from django.db import connection
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, override_settings
from django_tenants.test.cases import TenantTestCase
from django.utils import timezone

from .forms import DeploymentMarkerForm, MonitorForm, MonitorGroupForm, normalize_http_target, normalize_ping_target, normalize_socket_target, parse_http_codes, validate_host
from .time_display import validated_zone
from .models import CheckResult, Delivery, HourlySummary, Incident, MaintenanceWindow, Monitor, MonitorGroup, WorkerHeartbeat
from .maintenance import window_active
from .worker_health import worker_health
from .management.commands.check_monitoring_worker import _send_bitrix as _send_worker_bitrix
from .services import _next_scheduled_check, execute_monitor
from .retention import compact_history
from .deliveries import _bitrix_incident_fields, _send_bitrix, bitrix_deal_url, deliver_pending, delivery_error_message, send_test_email, sync_bitrix_resolutions, test_bitrix_connection, test_smtp_connection
from .checks import http_check, ping, tcp_check, tls_check
from .availability import availability_history
from .evidence import decrypt_evidence, encrypt_evidence, json_evidence
from .views import dashboard, delete_monitor, hourly_history, incident_detail, information, live_status, monitor_availability_data, monitor_detail_data, retry_delivery, test_email_delivery, test_notification_connection, toggle_active


def bitrix_ticket_metadata():
    return {"result": {"fields": {
        "UF_CRM_1675705962": {"title": "Asunto", "type": "string"},
        "UF_CRM_1651255181856": {"title": "Criticidad", "type": "enumeration", "items": [
            {"ID": "714", "VALUE": "Baja"}, {"ID": "716", "VALUE": "Media"}, {"ID": "1360", "VALUE": "Alta"},
        ]},
        "UF_CRM_1774028164424": {"title": "Origen Ticket", "type": "enumeration", "items": [
            {"ID": "7262", "VALUE": "Monitoreo Passing"},
        ]},
        "UF_CRM_1725892589": {"title": "Tipo Ticket", "type": "enumeration", "items": [
            {"ID": "6890", "VALUE": "Incidente de Disponibilidad"},
        ]},
    }}}


class CheckScheduleTests(SimpleTestCase):
    def test_completion_time_does_not_shift_the_minute_cadence(self):
        scheduled = datetime(2026, 10, 15, 12, 0, tzinfo=dt_timezone.utc)
        finished = scheduled + timedelta(seconds=5)
        self.assertEqual(_next_scheduled_check(scheduled, 60, finished), scheduled + timedelta(minutes=1))

    def test_overdue_checks_skip_missed_slots_without_catching_up_in_a_burst(self):
        scheduled = datetime(2026, 10, 15, 12, 0, tzinfo=dt_timezone.utc)
        finished = scheduled + timedelta(seconds=127)
        self.assertEqual(_next_scheduled_check(scheduled, 60, finished), scheduled + timedelta(minutes=3))


class ValidationTests(SimpleTestCase):
    def test_deployment_datetime_uses_selected_timezone(self):
        with timezone.override("Europe/Rome"):
            form = DeploymentMarkerForm(data={"deployed_at": "2026-09-30T12:30", "version": "V46", "note": ""})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["deployed_at"].isoformat(), "2026-09-30T12:30:00+02:00")
        self.assertIsNone(validated_zone("../etc/passwd"))
        self.assertEqual(validated_zone("Europe/Rome"), "Europe/Rome")

    def test_daily_maintenance_keeps_rome_hour_across_summer_time(self):
        from datetime import datetime, timezone as dt_timezone
        start = datetime(2026, 3, 28, 8, 0, tzinfo=dt_timezone.utc)
        window = MaintenanceWindow(starts_at=start, ends_at=start + timedelta(hours=1), recurrence=MaintenanceWindow.Recurrence.DAILY, time_zone="Europe/Rome")
        self.assertTrue(window_active(window, datetime(2026, 3, 29, 7, 30, tzinfo=dt_timezone.utc)))

    def test_daily_maintenance_includes_overnight_and_respects_first_start(self):
        from datetime import datetime, timezone as dt_timezone
        start = datetime(2026, 1, 5, 23, 0, tzinfo=dt_timezone.utc)
        window = MaintenanceWindow(starts_at=start, ends_at=start + timedelta(hours=2), recurrence=MaintenanceWindow.Recurrence.DAILY, enabled=True)
        self.assertFalse(window_active(window, start - timedelta(minutes=1)))
        self.assertTrue(window_active(window, start + timedelta(minutes=30)))
        self.assertTrue(window_active(window, start + timedelta(days=1, minutes=30)))
        self.assertFalse(window_active(window, start + timedelta(days=1, hours=2)))

    def test_weekly_maintenance_only_matches_same_weekday(self):
        from datetime import datetime, timezone as dt_timezone
        start = datetime(2026, 1, 5, 23, 0, tzinfo=dt_timezone.utc)
        window = MaintenanceWindow(starts_at=start, ends_at=start + timedelta(hours=2), recurrence=MaintenanceWindow.Recurrence.WEEKLY, enabled=True)
        self.assertTrue(window_active(window, start + timedelta(days=7, minutes=30)))
        self.assertFalse(window_active(window, start + timedelta(days=1, minutes=30)))

    def test_heartbeat_form_accepts_no_target_and_rejects_bad_interval(self):
        data = {"name": "Backup", "kind": "heartbeat", "heartbeat_interval_minutes": "60", "heartbeat_grace_minutes": "10", "interval_seconds": "60", "timeout_seconds": "3", "failure_threshold": "3", "recovery_threshold": "2"}
        form = MonitorForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["failure_threshold"], 1)
        self.assertEqual(form.cleaned_data["host"], "Señal entrante")
        data["heartbeat_interval_minutes"] = "10081"
        self.assertFalse(MonitorForm(data=data).is_valid())

    def test_delivery_errors_are_actionable_and_do_not_expose_secrets(self):
        error = smtplib.SMTPAuthenticationError(535, b"token=secret")
        message = delivery_error_message(error, Delivery.Channel.EMAIL)
        self.assertIn("Autenticación SMTP", message)
        self.assertNotIn("secret", message)
        self.assertIn("webhook", delivery_error_message("RuntimeError", Delivery.Channel.BITRIX))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST_USER="user", EMAIL_HOST_PASSWORD="secret")
    @patch("monitoring.deliveries.get_connection")
    def test_smtp_connection_only_opens_and_closes(self, get_connection_mock):
        test_smtp_connection()
        get_connection_mock.return_value.open.assert_called_once()
        get_connection_mock.return_value.close.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST_USER="user", EMAIL_HOST_PASSWORD="secret")
    @patch("monitoring.deliveries.send_mail", return_value=1)
    def test_email_delivery_sends_only_fixed_test_content(self, send_mail_mock):
        send_test_email("admin@example.com")
        self.assertEqual(send_mail_mock.call_args.args[3], ["admin@example.com"])
        self.assertNotIn("secret", send_mail_mock.call_args.args[1])

    @patch("monitoring.deliveries.requests.post")
    @patch("monitoring.deliveries.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_bitrix_connection_is_read_only(self, getenv, post):
        post.return_value.json.return_value = bitrix_ticket_metadata()
        test_bitrix_connection()
        self.assertTrue(post.call_args.args[0].endswith("/crm.item.fields.json"))
        self.assertEqual(post.call_args.kwargs["json"], {"entityTypeId": 2, "useOriginalUfNames": "Y"})

    @patch("monitoring.deliveries.requests.post")
    def test_bitrix_missing_options_report_the_exact_field(self, post):
        for code, label, option in (
            ("UF_CRM_1651255181856", "Criticidad", "Media"),
            ("UF_CRM_1774028164424", "Origen Ticket", "Monitoreo Passing"),
            ("UF_CRM_1725892589", "Tipo Ticket", "Incidente de Disponibilidad"),
        ):
            with self.subTest(field=label):
                data = bitrix_ticket_metadata()
                data["result"]["fields"][code]["items"] = []
                post.return_value.json.return_value = data
                with self.assertRaisesRegex(RuntimeError, f"{label} con la opción {option}") as caught:
                    _bitrix_incident_fields("https://example.com/rest/1/secret", "Prueba")
                self.assertEqual(delivery_error_message(caught.exception, Delivery.Channel.BITRIX), str(caught.exception))

    @patch("monitoring.deliveries.requests.post")
    def test_bitrix_missing_subject_is_rejected(self, post):
        data = bitrix_ticket_metadata()
        del data["result"]["fields"]["UF_CRM_1675705962"]
        post.return_value.json.return_value = data
        with self.assertRaisesRegex(RuntimeError, "campo Asunto"):
            _bitrix_incident_fields("https://example.com/rest/1/secret", "Prueba")

    @patch("monitoring.management.commands.check_monitoring_worker.requests.post")
    @patch("monitoring.management.commands.check_monitoring_worker.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_worker_bitrix_creation_uses_same_ticket_fields(self, getenv, post):
        post.return_value.json.side_effect = [
            {"result": {"items": []}}, bitrix_ticket_metadata(),
            {"result": {"item": {"id": 123}}},
        ]
        heartbeat = WorkerHeartbeat(alert_opened_at=timezone.now())
        self.assertEqual(_send_worker_bitrix("tenant", heartbeat), "123")
        fields = post.call_args.kwargs["json"]["fields"]
        self.assertEqual(fields["categoryId"], 2)
        self.assertEqual(fields["UF_CRM_1651255181856"], 716)
        self.assertEqual(fields["UF_CRM_1774028164424"], 7262)
        self.assertEqual(fields["UF_CRM_1725892589"], 6890)
        self.assertEqual(fields["UF_CRM_1675705962"], fields["title"])
        self.assertIn("Último ciclo:", fields["comments"])
        self.assertNotIn("UF_CRM_1751302650", fields)

    def test_host_rejects_command_syntax(self):
        for host in ["example.com;cat /etc/passwd", "-c 10", "https://example.com", "example.com localhost"]:
            with self.assertRaises(Exception):
                validate_host(host)

    def test_recipients_are_normalized(self):
        form = MonitorForm(data={"name": "Servidor", "kind": "ping", "host": "example.com", "interval_seconds": 60, "timeout_seconds": 3, "failure_threshold": 3, "recovery_threshold": 2, "recipients": " a@example.com, b@example.com, a@example.com"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["recipients"], "a@example.com, b@example.com")

    def test_pasted_homepage_url_becomes_ping_host(self):
        self.assertEqual(normalize_ping_target("https://previ.com.ar/"), "previ.com.ar")
        self.assertEqual(normalize_ping_target("http://previ.com.ar"), "previ.com.ar")

    def test_ping_rejects_url_parts_it_would_ignore(self):
        for target in ["https://previ.com.ar/health", "https://previ.com.ar:8443", "https://user:secret@previ.com.ar", "https://previ.com.ar/?x=1"]:
            with self.assertRaises(Exception):
                normalize_ping_target(target)

    def test_http_target_accepts_endpoint_and_rejects_credentials_or_query(self):
        self.assertEqual(normalize_http_target("https://previ.com.ar/health"), "https://previ.com.ar/health")
        for target in ["ftp://example.com/health", "https://user:secret@example.com/health", "https://example.com/health?token=secret", "https://example.com/#fragment", "https://example.com:abc/", "https://example.com\\@other.example/"]:
            with self.assertRaises(Exception):
                normalize_http_target(target)

    def test_http_monitor_form_keeps_endpoint_url(self):
        form = MonitorForm(data={"name": "API", "kind": "http", "host": "https://previ.com.ar/health", "interval_seconds": 60, "timeout_seconds": 3, "failure_threshold": 3, "recovery_threshold": 2, "recipients": ""})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["host"], "https://previ.com.ar/health")

    def test_http_rules_validate_codes_and_json_pair(self):
        self.assertEqual(parse_http_codes("200-201,301"), {200, 201, 301})
        for codes in ("99", "600", "301-200", "200,,301"):
            with self.assertRaises(Exception):
                parse_http_codes(codes)
        data = {"name": "API", "kind": "http", "host": "https://example.com/health", "interval_seconds": 60, "timeout_seconds": 3, "failure_threshold": 3, "recovery_threshold": 2, "recipients": "", "expected_http_codes": "200,301", "max_latency_ms": 250, "json_path": "health.status", "json_expected_value": '"ok"'}
        self.assertTrue(MonitorForm(data=data).is_valid())
        self.assertTrue(MonitorForm(data={**data, "json_path": "0.status"}).is_valid())
        self.assertFalse(MonitorForm(data={**data, "json_expected_value": "ok"}).is_valid())
        self.assertFalse(MonitorForm(data={**data, "json_path": "health[0]"}).is_valid())
        self.assertFalse(MonitorForm(data={**data, "json_expected_value": ""}).is_valid())

    def test_tcp_and_tls_targets_are_normalized(self):
        self.assertEqual(normalize_socket_target("example.com:5432"), "example.com:5432")
        self.assertEqual(normalize_socket_target("example.com", default_port=443), "example.com:443")
        self.assertEqual(normalize_socket_target("[2001:db8::1]:443"), "[2001:db8::1]:443")
        for target in ("https://example.com", "example.com:0", "example.com:65536", "user@example.com:443", "2001:db8::1:443"):
            with self.assertRaises(Exception):
                normalize_socket_target(target)
        common = {"name": "Puerto", "interval_seconds": 60, "timeout_seconds": 3, "failure_threshold": 3, "recovery_threshold": 2, "recipients": ""}
        tcp_form = MonitorForm(data={**common, "kind": "tcp", "host": "example.com:5432"})
        tls_form = MonitorForm(data={**common, "kind": "tls", "host": "example.com", "tls_min_days": 14})
        self.assertTrue(tcp_form.is_valid(), tcp_form.errors)
        ping_form = MonitorForm(data={**common, "kind": "ping", "host": "example.com", "max_latency_ms": 200})
        self.assertTrue(ping_form.is_valid(), ping_form.errors)
        self.assertEqual(ping_form.cleaned_data["max_latency_ms"], 200)
        self.assertTrue(tls_form.is_valid(), tls_form.errors)
        self.assertEqual(tls_form.cleaned_data["host"], "example.com:443")

    @patch("monitoring.checks.requests.Session")
    def test_http_check_classifies_codes_without_following_redirects_or_reading_body(self, session_class):
        session = session_class.return_value
        response = MagicMock()
        session.get.return_value = response
        for code, expected, reason in [(200, CheckResult.Status.OK, "HTTP 200"), (301, CheckResult.Status.FAILURE, "Redirección HTTP 301"), (401, CheckResult.Status.FAILURE, "Autenticación requerida (HTTP 401)"), (500, CheckResult.Status.FAILURE, "Error del servidor (HTTP 500)")]:
            response.status_code = code
            status, latency, detail, actual_code = http_check("https://example.com/health", 3)
            self.assertEqual((status, detail, actual_code), (expected, reason, code))
            self.assertIsNotNone(latency)
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_args.kwargs["allow_redirects"], False)
        self.assertEqual(session.get.call_args.kwargs["stream"], True)
        self.assertEqual(session.get.call_args.kwargs["timeout"], 3)
        self.assertEqual(response.close.call_count, 4)

    @patch("monitoring.checks.requests.Session")
    def test_http_timeout_is_a_service_failure(self, session_class):
        import requests
        session_class.return_value.get.side_effect = requests.exceptions.Timeout()
        self.assertEqual(http_check("https://example.com/health", 3), (CheckResult.Status.FAILURE, None, "Tiempo de espera agotado", None))

    @patch("monitoring.checks.requests.Session")
    def test_http_accepts_configured_redirect_without_reading_body(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 301
        self.assertEqual(http_check("https://example.com/health", 3, "200-299,301")[0], CheckResult.Status.OK)
        response.iter_content.assert_not_called()

    @patch("monitoring.checks.requests.Session")
    def test_http_rejects_wrong_json_and_never_returns_body(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.iter_content.return_value = [b'{"health":{"status":"down","token":"secret"}}']
        result = http_check("https://example.com/health", 3, json_path="health.status", json_expected_value='"ok"')
        self.assertEqual(result[0], CheckResult.Status.FAILURE)
        self.assertEqual(result[3], 200)
        self.assertNotIn("secret", result[2])
        response.close.assert_called_once()

    @patch("monitoring.checks.requests.Session")
    def test_http_accepts_matching_nested_json_value(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 200
        response.headers = {}
        response.iter_content.return_value = [b'{"items":[{"healthy":true}]}']
        result = http_check("https://example.com/health", 3, json_path="items.0.healthy", json_expected_value="true")
        self.assertEqual((result[0], result[2], result[3]), (CheckResult.Status.OK, "HTTP 200", 200))

    @patch("monitoring.checks.requests.Session")
    def test_http_accepts_root_json_list_path(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 200
        response.headers = {}
        response.iter_content.return_value = [b'[{"status":"ok"},{"status":"down"}]']
        result = http_check("https://example.com/health", 3, json_path="0.status", json_expected_value='"ok"')
        self.assertEqual(result[0], CheckResult.Status.OK)

    @patch("monitoring.checks.requests.Session")
    def test_http_distinguishes_invalid_json_from_missing_path(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 200
        response.headers = {}
        response.iter_content.return_value = [b'[{"name":"Leanne Graham"}]']
        missing = http_check("https://example.com/users", 3, json_path="json.0.name", json_expected_value='"Leanne Graham"')
        self.assertEqual(missing[2], "Ruta JSON no encontrada: json.0.name")
        response.iter_content.return_value = [b'<html>error</html>']
        invalid = http_check("https://example.com/users", 3, json_path="0.name", json_expected_value='"Leanne Graham"')
        self.assertEqual(invalid[2], "La respuesta no es JSON válido")

    @patch("monitoring.checks.requests.Session")
    def test_http_failure_captures_redacted_json_only_when_requested(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 500
        response.headers = {"Content-Type": "application/json"}
        response.iter_content.return_value = [b'{"error":"down","token":"secret-value","email":"a@example.com"}']
        self.assertEqual(len(http_check("https://example.com/health", 3)), 4)
        result = http_check("https://example.com/health", 3, capture_json=True)
        self.assertEqual(result[0], CheckResult.Status.FAILURE)
        self.assertEqual(len(result), 5)
        self.assertIn('"error": "down"', result[4][0])
        self.assertNotIn("secret-value", result[4][0])
        self.assertNotIn("a@example.com", result[4][0])

    def test_evidence_encryption_round_trip(self):
        text, truncated = json_evidence({"status": "down", "api_key": "secret"})
        token = encrypt_evidence(text)
        self.assertNotIn("down", token)
        self.assertEqual(decrypt_evidence(token), text)
        self.assertFalse(truncated)

    @patch("monitoring.checks.requests.Session")
    def test_http_limits_json_body(self, session_class):
        response = session_class.return_value.get.return_value
        response.status_code = 200
        response.headers = {}
        response.iter_content.return_value = [b"x" * (16 * 1024 + 1)]
        result = http_check("https://example.com/health", 3, json_path="status", json_expected_value='"ok"')
        self.assertEqual(result[0], CheckResult.Status.FAILURE)
        self.assertEqual(result[2], "Respuesta JSON demasiado grande")

    @patch("monitoring.checks.time.monotonic", side_effect=[0, 0.3])
    @patch("monitoring.checks.requests.Session")
    def test_http_latency_limit_marks_successful_code_as_slow(self, session_class, monotonic):
        session_class.return_value.get.return_value.status_code = 200
        result = http_check("https://example.com/health", 3, max_latency_ms=250)
        self.assertEqual((result[0], result[1], result[3]), (CheckResult.Status.SLOW, 300, 200))

    @patch("monitoring.checks.socket.create_connection")
    def test_tcp_check_classifies_open_and_refused_port(self, create_connection):
        result = tcp_check("example.com:5432", 3)
        self.assertEqual(result[0], CheckResult.Status.OK)
        create_connection.assert_called_with(("example.com", 5432), timeout=3)
        create_connection.side_effect = ConnectionRefusedError()
        self.assertEqual(tcp_check("example.com:5432", 3)[0], CheckResult.Status.FAILURE)

    @patch("monitoring.checks.ssl.cert_time_to_seconds")
    @patch("monitoring.checks.ssl.create_default_context")
    @patch("monitoring.checks.socket.create_connection")
    def test_tls_check_verifies_expiry_without_storing_certificate(self, create_connection, create_context, cert_time):
        import time
        cert_time.return_value = time.time() + 40 * 86400
        secure = create_context.return_value.wrap_socket.return_value.__enter__.return_value
        secure.getpeercert.return_value = {"notAfter": "certificate-date"}
        healthy = tls_check("example.com:443", 3, 30)
        self.assertEqual(healthy[0], CheckResult.Status.OK)
        create_context.return_value.wrap_socket.assert_called_with(create_connection.return_value.__enter__.return_value, server_hostname="example.com")
        cert_time.return_value = time.time() + 10 * 86400
        expiring = tls_check("example.com:443", 3, 30)
        self.assertEqual(expiring[0], CheckResult.Status.FAILURE)
        self.assertIn("vence", expiring[2])
        self.assertNotIn("certificate-date", expiring[2])

    @patch("monitoring.checks.subprocess.run")
    @patch("monitoring.checks.platform.system", return_value="Windows")
    def test_windows_ping_uses_millisecond_timeout(self, system, run):
        run.return_value.returncode = 0
        status, latency, detail = ping("previ.com.ar", 3)
        self.assertEqual(status, CheckResult.Status.OK)
        self.assertIsNotNone(latency)
        self.assertEqual(run.call_args.args[0], ["ping", "-n", "1", "-w", "3000", "previ.com.ar"])

    @patch("monitoring.checks.subprocess.run")
    @patch("monitoring.checks.platform.system", return_value="Linux")
    def test_linux_ping_keeps_second_timeout(self, system, run):
        run.return_value.returncode = 1
        status, latency, detail = ping("previ.com.ar", 3)
        self.assertEqual(status, CheckResult.Status.FAILURE)
        self.assertEqual(run.call_args.args[0], ["ping", "-n", "-c", "1", "-W", "3", "--", "previ.com.ar"])


class IncidentStateTests(TenantTestCase):
    @patch("monitoring.services.run_check")
    def test_slow_response_opens_distinct_incident_and_recovers(self, check):
        monitor = Monitor.objects.create(
            name="Ping lento", kind=Monitor.Kind.PING, host="example.com",
            max_latency_ms=200, failure_threshold=2, recovery_threshold=2,
        )
        check.return_value = (CheckResult.Status.OK, 280, "")
        first = execute_monitor(monitor.pk)
        self.assertEqual((first.status, first.latency_ms), (CheckResult.Status.SLOW, 280))
        self.assertEqual(Incident.objects.count(), 0)
        execute_monitor(monitor.pk)
        monitor.refresh_from_db()
        self.assertEqual(monitor.state, Monitor.State.SLOW)
        incident = Incident.objects.get(monitor=monitor)
        self.assertEqual(incident.kind, Incident.Kind.SLOW)
        self.assertEqual(Delivery.objects.filter(incident=incident, event='opened', channel='bitrix').count(), 1)
        self.assertEqual(availability_history(monitor, 1)['totals']['downtime_seconds'], 0)
        check.return_value = (CheckResult.Status.OK, 80, "")
        execute_monitor(monitor.pk)
        execute_monitor(monitor.pk)
        incident.refresh_from_db()
        self.assertIsNotNone(incident.recovered_at)
        monitor.refresh_from_db()
        self.assertEqual(monitor.state, Monitor.State.UP)

    @patch("monitoring.services.run_check")
    def test_slow_response_escalates_to_outage_without_mixing_incidents(self, check):
        monitor = Monitor.objects.create(
            name="API", kind=Monitor.Kind.HTTP, host="https://example.com",
            max_latency_ms=200, failure_threshold=1,
        )
        check.return_value = (CheckResult.Status.SLOW, 350, "Latencia alta", 200)
        execute_monitor(monitor.pk)
        slow = Incident.objects.get(monitor=monitor)
        check.return_value = (CheckResult.Status.FAILURE, 350, "HTTP 500", 500)
        execute_monitor(monitor.pk)
        slow.refresh_from_db()
        self.assertIsNotNone(slow.recovered_at)
        self.assertEqual(slow.end_reason, Incident.EndReason.ESCALATED)
        self.assertEqual(slow.end_label, "Escaló a caída")
        outage = Incident.objects.get(monitor=monitor, recovered_at__isnull=True)
        self.assertEqual(outage.kind, Incident.Kind.FAILURE)
        monitor.refresh_from_db()
        self.assertEqual(monitor.state, Monitor.State.DOWN)

    @patch("monitoring.services.run_check")
    def test_incident_keeps_first_encrypted_json_sample(self, check):
        monitor = Monitor.objects.create(name="API", kind=Monitor.Kind.HTTP, host="https://example.com", failure_threshold=1)
        check.return_value = (CheckResult.Status.FAILURE, 25, "HTTP 500", 500, ('{"status":"down"}', False))
        execute_monitor(monitor.pk)
        incident = Incident.objects.get(monitor=monitor)
        first_token = incident.json_evidence_encrypted
        self.assertTrue(first_token)
        self.assertNotIn("down", first_token)
        self.assertEqual(decrypt_evidence(first_token), '{"status":"down"}')
        check.return_value = (CheckResult.Status.FAILURE, 25, "HTTP 500", 500, ('{"status":"worse"}', False))
        execute_monitor(monitor.pk)
        incident.refresh_from_db()
        self.assertEqual(incident.json_evidence_encrypted, first_token)

    @patch("monitoring.views.render", return_value=HttpResponse(status=200))
    def test_incident_json_is_only_decrypted_for_authorized_view(self, render_view):
        monitor = Monitor.objects.create(name="API", kind=Monitor.Kind.HTTP, host="https://example.com")
        incident = Incident.objects.create(monitor=monitor, json_evidence_encrypted=encrypt_evidence('{"status":"down"}'))
        request = RequestFactory().get(f"/monitoring/incidents/{incident.pk}/")
        request.user = get_user_model().objects.create_user(username="evidence-viewer", email="evidence-viewer@example.test", password="test-password")
        self.assertEqual(incident_detail(request, incident.pk).status_code, 403)
        render_view.assert_not_called()
        request.user = get_user_model().objects.create_superuser(username="evidence-admin", email="evidence-admin@example.test", password="test-password")
        self.assertEqual(incident_detail(request, incident.pk).status_code, 200)
        self.assertEqual(render_view.call_args.args[2]["json_evidence"], '{"status":"down"}')

    def test_information_requires_monitoring_permission(self):
        request = RequestFactory().get("/monitoring/information/")
        request.user = get_user_model().objects.create_user(username="info-viewer", password="test-password")
        self.assertEqual(information(request).status_code, 403)

    @patch("monitoring.views.redirect", return_value=HttpResponse(status=302))
    @patch("monitoring.views.messages.success")
    def test_retry_failed_delivery_resets_attempts_and_schedules_now(self, message, redirect_view):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        incident = Incident.objects.create(monitor=monitor)
        delivery = Delivery.objects.create(incident=incident, channel=Delivery.Channel.EMAIL, event="opened", status="failed", attempts=10, last_error="SMTPAuthenticationError", next_attempt_at=timezone.now() + timedelta(hours=1))
        user = get_user_model().objects.create_superuser(username="retry-admin", password="test-password")
        request = RequestFactory().post(f"/monitoring/deliveries/{delivery.pk}/retry/")
        request.user = user
        self.assertEqual(retry_delivery(request, delivery.pk).status_code, 302)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.attempts), ("pending", 0))
        self.assertLess(abs((timezone.now() - delivery.next_attempt_at).total_seconds()), 5)

    def test_retry_delivery_requires_permission(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        delivery = Delivery.objects.create(incident=Incident.objects.create(monitor=monitor), channel=Delivery.Channel.EMAIL, event="opened")
        request = RequestFactory().post(f"/monitoring/deliveries/{delivery.pk}/retry/")
        request.user = get_user_model().objects.create_user(username="retry-viewer", password="test-password")
        self.assertEqual(retry_delivery(request, delivery.pk).status_code, 403)

    @patch("monitoring.views.redirect", return_value=HttpResponse(status=302))
    @patch("monitoring.views.messages.success")
    @patch("monitoring.views.test_smtp_connection")
    def test_notification_connection_action_does_not_send(self, smtp_check, message, redirect_view):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        incident = Incident.objects.create(monitor=monitor)
        request = RequestFactory().post(f"/monitoring/incidents/{incident.pk}/test/email/")
        request.user = get_user_model().objects.create_superuser(username="notification-admin", password="test-password")
        self.assertEqual(test_notification_connection(request, incident.pk, "email").status_code, 302)
        smtp_check.assert_called_once()

    @patch("monitoring.views.redirect", return_value=HttpResponse(status=302))
    @patch("monitoring.views.messages.success")
    @patch("monitoring.views.messages.error")
    @patch("monitoring.views.send_test_email")
    def test_test_email_only_accepts_user_or_monitor_recipient(self, send_email, error, success, redirect_view):
        monitor = Monitor.objects.create(name="Servidor", host="example.com", recipients="allowed@example.com")
        incident = Incident.objects.create(monitor=monitor)
        user = get_user_model().objects.create_superuser(username="mail-admin", email="admin@example.com", password="test-password")
        request = RequestFactory().post(f"/monitoring/incidents/{incident.pk}/test-email/", {"email": "other@example.com"})
        request.user = user
        test_email_delivery(request, incident.pk)
        send_email.assert_not_called()
        request = RequestFactory().post(f"/monitoring/incidents/{incident.pk}/test-email/", {"email": "allowed@example.com"})
        request.user = user
        test_email_delivery(request, incident.pk)
        send_email.assert_called_once_with("allowed@example.com")

    @patch("monitoring.deliveries._send_email", side_effect=smtplib.SMTPAuthenticationError(535, b"secret"))
    def test_failed_email_delivery_stores_safe_reason(self, send_email):
        monitor = Monitor.objects.create(name="Servidor", host="example.com", recipients="admin@example.com")
        delivery = Delivery.objects.create(incident=Incident.objects.create(monitor=monitor), channel=Delivery.Channel.EMAIL, event="opened")
        deliver_pending()
        delivery.refresh_from_db()
        self.assertIn("Autenticación SMTP", delivery.last_error)
        self.assertNotIn("secret", delivery.last_error)

    @patch("monitoring.views.render", return_value=HttpResponse(status=200))
    @patch("monitoring.views.redirect", return_value=HttpResponse(status=302))
    @patch("monitoring.views.messages.success")
    def test_delete_monitor_requires_confirmation_and_cascades_history(self, message, redirect_view, render_view):
        monitor = Monitor.objects.create(name="Borrar", host="example.com")
        other = Monitor.objects.create(name="Conservar", host="other.example.com")
        CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.FAILURE)
        HourlySummary.objects.create(monitor=monitor, hour=timezone.now())
        incident = Incident.objects.create(monitor=monitor)
        Delivery.objects.create(incident=incident, channel=Delivery.Channel.EMAIL, event="opened")
        CheckResult.objects.create(monitor=other, status=CheckResult.Status.OK)
        user = get_user_model().objects.create_superuser(username="delete-admin", password="test-password")
        get_request = RequestFactory().get(f"/monitoring/{monitor.pk}/delete/")
        get_request.user = user
        self.assertEqual(delete_monitor(get_request, monitor.pk).status_code, 200)
        self.assertTrue(Monitor.objects.filter(pk=monitor.pk).exists())
        context = render_view.call_args.args[2]
        self.assertEqual((context["check_count"], context["incident_count"]), (1, 1))
        post_request = RequestFactory().post(f"/monitoring/{monitor.pk}/delete/")
        post_request.user = user
        self.assertEqual(delete_monitor(post_request, monitor.pk).status_code, 302)
        self.assertFalse(Monitor.objects.filter(pk=monitor.pk).exists())
        self.assertEqual(CheckResult.objects.filter(monitor=monitor).count(), 0)
        self.assertEqual(HourlySummary.objects.filter(monitor=monitor).count(), 0)
        self.assertEqual(Incident.objects.filter(monitor=monitor).count(), 0)
        self.assertEqual(Delivery.objects.filter(incident=incident).count(), 0)
        self.assertTrue(Monitor.objects.filter(pk=other.pk).exists())

    def test_delete_monitor_rejects_user_without_permission(self):
        monitor = Monitor.objects.create(name="Protegido", host="example.com")
        user = get_user_model().objects.create_user(username="delete-viewer", password="test-password")
        request = RequestFactory().post(f"/monitoring/{monitor.pk}/delete/")
        request.user = user
        self.assertEqual(delete_monitor(request, monitor.pk).status_code, 403)
        self.assertTrue(Monitor.objects.filter(pk=monitor.pk).exists())

    @patch("monitoring.views.redirect", return_value=HttpResponse(status=302))
    @patch("monitoring.views.messages.success")
    def test_stop_and_start_monitor(self, message, redirect_view):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        user = get_user_model().objects.create_superuser(username="toggle-admin", password="test-password")
        request = RequestFactory().post(f"/monitoring/{monitor.pk}/toggle/")
        request.user = user
        toggle_active(request, monitor.pk)
        monitor.refresh_from_db()
        self.assertFalse(monitor.enabled)
        self.assertIsNone(monitor.check_started_at)
        toggle_active(request, monitor.pk)
        monitor.refresh_from_db()
        self.assertTrue(monitor.enabled)
        self.assertEqual(monitor.state, Monitor.State.UNKNOWN)
        self.assertLess((timezone.now() - monitor.next_check_at).total_seconds(), 5)

    def test_user_without_permission_cannot_stop_monitor(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        user = get_user_model().objects.create_user(username="toggle-viewer", password="test-password")
        request = RequestFactory().post(f"/monitoring/{monitor.pk}/toggle/")
        request.user = user
        self.assertEqual(toggle_active(request, monitor.pk).status_code, 403)
        monitor.refresh_from_db()
        self.assertTrue(monitor.enabled)

    @patch("monitoring.services.run_check")
    def test_check_is_visible_as_running_then_cleared(self, check):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")

        def during_check(item):
            item.refresh_from_db()
            self.assertIsNotNone(item.check_started_at)
            return CheckResult.Status.OK, 7, ""

        check.side_effect = during_check
        execute_monitor(monitor.pk)
        monitor.refresh_from_db()
        self.assertIsNone(monitor.check_started_at)
        self.assertEqual(monitor.last_status, CheckResult.Status.OK)

    def test_live_status_exposes_current_check_to_admin(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com", check_started_at=timezone.now())
        user = get_user_model().objects.create_superuser(username="monitor-admin", password="test-password")
        request = RequestFactory().get("/monitoring/live/")
        request.user = user
        payload = json.loads(live_status(request).content)
        self.assertEqual(payload["monitors"][0]["id"], monitor.pk)
        self.assertTrue(payload["monitors"][0]["running"])

    def test_worker_health_uses_heartbeat_and_counts_overdue_checks(self):
        now = timezone.now()
        monitor = Monitor.objects.create(name="Servidor", host="example.com", next_check_at=now - timedelta(minutes=4))
        WorkerHeartbeat.objects.create(pk=1, last_cycle_at=now - timedelta(seconds=10))
        health = worker_health([monitor], now)
        self.assertTrue(health["worker_recent"])
        self.assertEqual(health["overdue_count"], 1)
        WorkerHeartbeat.objects.filter(pk=1).update(last_cycle_at=now - timedelta(minutes=4))
        self.assertFalse(worker_health([monitor], now)["worker_recent"])

    @patch("monitoring.management.commands.check_monitoring_worker.requests.post")
    @patch("monitoring.management.commands.check_monitoring_worker.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_worker_bitrix_alert_reuses_existing_deal(self, getenv, post):
        heartbeat = WorkerHeartbeat(alert_opened_at=timezone.now())
        post.return_value.json.return_value = {"result": {"items": [{"id": 123}]}}
        self.assertEqual(_send_worker_bitrix("tenant", heartbeat), "123")
        post.assert_called_once()
        self.assertIn("originId", post.call_args.kwargs["json"]["filter"])

    @patch("monitoring.management.commands.check_monitoring_worker._send_bitrix", return_value="123")
    @patch("monitoring.management.commands.check_monitoring_worker.send_mail", return_value=1)
    @patch("monitoring.management.commands.check_monitoring_worker._alert_emails", return_value=["admin@example.com"])
    @patch("monitoring.management.commands.check_monitoring_worker.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    @patch("monitoring.management.commands.check_monitoring_worker.tenant_context", side_effect=lambda tenant: nullcontext())
    @patch("monitoring.management.commands.check_monitoring_worker.get_tenant_model")
    def test_watchdog_deduplicates_and_rearms_after_recovery(self, tenant_model, tenant_context, getenv, emails, send_mail_mock, bitrix_mock):
        tenant_model.return_value.objects.exclude.return_value = [MagicMock(schema_name="tenant")]
        Monitor.objects.create(name="Servidor", host="example.com", next_check_at=timezone.now() - timedelta(minutes=5))
        call_command("check_monitoring_worker", verbosity=0)
        call_command("check_monitoring_worker", verbosity=0)
        self.assertEqual(send_mail_mock.call_count, 1)
        self.assertEqual(bitrix_mock.call_count, 1)
        Monitor.objects.update(next_check_at=timezone.now() + timedelta(minutes=1))
        WorkerHeartbeat.objects.filter(pk=1).update(last_cycle_at=timezone.now())
        call_command("check_monitoring_worker", verbosity=0)
        self.assertIsNone(WorkerHeartbeat.objects.get(pk=1).alert_opened_at)
        WorkerHeartbeat.objects.filter(pk=1).update(last_cycle_at=timezone.now() - timedelta(minutes=4))
        call_command("check_monitoring_worker", verbosity=0)
        self.assertEqual(send_mail_mock.call_count, 2)
        self.assertEqual(bitrix_mock.call_count, 2)

    def test_live_status_rejects_user_without_permission(self):
        user = get_user_model().objects.create_user(username="monitor-viewer", password="test-password")
        request = RequestFactory().get("/monitoring/live/")
        request.user = user
        self.assertEqual(live_status(request).status_code, 403)

    def test_live_status_lists_only_ten_recent_checks(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        for index in range(12):
            CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.OK, latency_ms=index)
        user = get_user_model().objects.create_superuser(username="recent-admin", password="test-password")
        request = RequestFactory().get("/monitoring/live/")
        request.user = user
        payload = json.loads(live_status(request).content)
        self.assertEqual(len(payload["recent"]), 10)

    @patch("monitoring.services.run_check")
    def test_http_result_preserves_code_and_reason(self, check):
        monitor = Monitor.objects.create(name="API", kind=Monitor.Kind.HTTP, host="https://example.com/health", failure_threshold=1)
        check.return_value = (CheckResult.Status.FAILURE, 42, "Error del servidor (HTTP 500)", 500)
        result = execute_monitor(monitor.pk)
        monitor.refresh_from_db()
        self.assertEqual((result.http_status_code, result.detail, result.latency_ms), (500, "Error del servidor (HTTP 500)", 42))
        self.assertEqual((monitor.last_http_status_code, monitor.last_detail), (500, "Error del servidor (HTTP 500)"))
        self.assertEqual(monitor.state, Monitor.State.DOWN)

    def test_monitor_detail_data_is_scoped_and_has_latency_history(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        other = Monitor.objects.create(name="Otro", host="other.example.com")
        CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.OK, latency_ms=18, detail="HTTP 200", http_status_code=200)
        CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.FAILURE, detail="Error del servidor (HTTP 500)", http_status_code=500)
        CheckResult.objects.create(monitor=other, status=CheckResult.Status.OK, latency_ms=99)
        user = get_user_model().objects.create_superuser(username="detail-admin", password="test-password")
        request = RequestFactory().get(f"/monitoring/{monitor.pk}/data/?hours=1", {"hours": "1"})
        request.user = user
        payload = json.loads(monitor_detail_data(request, monitor.pk).content)
        self.assertEqual(len(payload["slots"]), 60)
        self.assertEqual([item["latency_ms"] for item in payload["latencies"]], [18, None])
        self.assertEqual([item["http_status_code"] for item in payload["latencies"]], [200, 500])
        self.assertEqual(len(payload["recent"]), 2)

    def test_monitor_detail_data_rejects_unprivileged_user_and_bad_range(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        user = get_user_model().objects.create_user(username="detail-viewer", email="detail-viewer@example.test", password="test-password")
        request = RequestFactory().get(f"/monitoring/{monitor.pk}/data/?hours=999", {"hours": "999"})
        request.user = user
        self.assertEqual(monitor_detail_data(request, monitor.pk).status_code, 403)
        request.user = get_user_model().objects.create_superuser(username="detail-range-admin", email="detail-range-admin@example.test", password="test-password")
        self.assertEqual(monitor_detail_data(request, monitor.pk).status_code, 400)

    def test_availability_combines_hourly_summary_checks_and_incidents(self):
        now = timezone.now()
        monitor = Monitor.objects.create(name="Historial", host="example.com")
        HourlySummary.objects.create(monitor=monitor, hour=now - timedelta(days=8), ok_count=3, latency_sum_ms=90, latency_count=3, latency_histogram={"50": 3})
        CheckResult.objects.create(monitor=monitor, checked_at=now - timedelta(minutes=2), status=CheckResult.Status.OK, latency_ms=10)
        CheckResult.objects.create(monitor=monitor, checked_at=now - timedelta(minutes=1), status=CheckResult.Status.FAILURE)
        CheckResult.objects.create(monitor=monitor, checked_at=now, status=CheckResult.Status.ERROR)
        Incident.objects.create(monitor=monitor, started_at=now - timedelta(hours=2), recovered_at=now - timedelta(hours=1))
        data = availability_history(monitor, 30, now)
        self.assertEqual((data["totals"]["ok"], data["totals"]["failure"], data["totals"]["error"]), (4, 1, 1))
        self.assertEqual(data["totals"]["availability_pct"], 80)
        self.assertEqual((data["totals"]["latency_avg_ms"], data["totals"]["latency_p95_ms"]), (25, 50))
        self.assertEqual(data["totals"]["downtime_seconds"], 3600)
        self.assertEqual(data["totals"]["incident_count"], 1)
        self.assertEqual(len(data["buckets"]), 30)
        self.assertEqual(len(availability_history(monitor, 1, now)["buckets"]), 24)
        self.assertEqual(len(availability_history(monitor, 7, now)["buckets"]), 7)
        self.assertEqual(len(availability_history(monitor, 365, now)["buckets"]), 53)

    def test_availability_marks_legacy_percentile_as_partial_and_checks_permission(self):
        now = timezone.now()
        monitor = Monitor.objects.create(name="Historial", host="example.com")
        HourlySummary.objects.create(monitor=monitor, hour=now - timedelta(days=8), ok_count=2, latency_sum_ms=20, latency_count=2)
        CheckResult.objects.create(monitor=monitor, checked_at=now - timedelta(seconds=1), status=CheckResult.Status.OK, latency_ms=10)
        data = availability_history(monitor, 365, now)
        self.assertEqual(data["totals"]["p95_coverage_pct"], 33)
        request = RequestFactory().get(f"/monitoring/{monitor.pk}/availability/?days=365", {"days": "365"})
        request.user = get_user_model().objects.create_user(username="availability-viewer", email="availability-viewer@example.test", password="test-password")
        self.assertEqual(monitor_availability_data(request, monitor.pk).status_code, 403)
        request.user = get_user_model().objects.create_superuser(username="availability-admin", email="availability-admin@example.test", password="test-password")
        self.assertEqual(monitor_availability_data(request, monitor.pk).status_code, 200)
        request.GET = {"days": "999"}
        self.assertEqual(monitor_availability_data(request, monitor.pk).status_code, 400)

    def test_hourly_history_has_60_slots_and_preserves_failures(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.OK, checked_at=timezone.now() - timedelta(minutes=2), latency_ms=12)
        CheckResult.objects.create(monitor=monitor, status=CheckResult.Status.FAILURE, checked_at=timezone.now())
        user = get_user_model().objects.create_superuser(username="history-admin", password="test-password")
        request = RequestFactory().get("/monitoring/history/")
        request.user = user
        payload = json.loads(hourly_history(request).content)
        slots = payload["histories"][0]["slots"]
        self.assertEqual(len(slots), 60)
        self.assertEqual({slot["status"] for slot in slots if slot}, {CheckResult.Status.OK, CheckResult.Status.FAILURE})
        self.assertEqual(sum(slot is None for slot in slots), 58)

    def test_hourly_history_rejects_user_without_permission(self):
        user = get_user_model().objects.create_user(username="history-viewer", password="test-password")
        request = RequestFactory().get("/monitoring/history/")
        request.user = user
        self.assertEqual(hourly_history(request).status_code, 403)

    @patch("monitoring.services.run_check")
    def test_one_incident_for_continuous_failure_and_recovery(self, check):
        monitor = Monitor.objects.create(name="Servidor", host="example.com", recipients="a@example.com")
        check.return_value = (CheckResult.Status.FAILURE, None, "Sin respuesta")
        for _ in range(5):
            execute_monitor(monitor.pk)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(Delivery.objects.filter(event="opened").count(), 2)
        monitor.refresh_from_db()
        self.assertEqual(monitor.state, Monitor.State.DOWN)
        check.return_value = (CheckResult.Status.OK, 5, "")
        execute_monitor(monitor.pk)
        execute_monitor(monitor.pk)
        self.assertIsNotNone(Incident.objects.get().recovered_at)
        self.assertEqual(Delivery.objects.filter(event="recovered").count(), 1)

    @patch("monitoring.services.run_check")
    def test_local_check_errors_do_not_open_incident(self, check):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        check.return_value = (CheckResult.Status.ERROR, None, "Falta ping")
        for _ in range(3):
            execute_monitor(monitor.pk)
        self.assertEqual(Incident.objects.count(), 0)

    def test_retention_compacts_old_successes_and_keeps_failures(self):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        old = timezone.now() - timedelta(days=8)
        CheckResult.objects.create(monitor=monitor, checked_at=old, status=CheckResult.Status.OK, latency_ms=10)
        CheckResult.objects.create(monitor=monitor, checked_at=old, status=CheckResult.Status.FAILURE)
        compact_history()
        self.assertEqual(CheckResult.objects.filter(status=CheckResult.Status.OK).count(), 0)
        self.assertEqual(CheckResult.objects.filter(status=CheckResult.Status.FAILURE).count(), 1)
        self.assertEqual(monitor.summaries.get().ok_count, 1)
        self.assertEqual(monitor.summaries.get().latency_histogram, {"10": 1})

    @patch("monitoring.deliveries.requests.post")
    @patch("monitoring.deliveries.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_bitrix_deal_is_created_once_in_tickets_previ(self, getenv, post):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        incident = Incident.objects.create(monitor=monitor)
        delivery = Delivery.objects.create(incident=incident, channel=Delivery.Channel.BITRIX, event="opened")
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.side_effect = [
            {"result": {"items": []}},
            bitrix_ticket_metadata(),
            {"result": {"item": {"id": 123}}},
        ]
        connection.schema_name = "test"
        _send_bitrix(delivery)
        incident.refresh_from_db()
        self.assertEqual(incident.bitrix_deal_id, "123")
        fields = post.call_args_list[2].kwargs["json"]["fields"]
        self.assertEqual(fields["categoryId"], 2)
        self.assertNotIn("UF_CRM_1751302650", fields)
        self.assertEqual(fields["UF_CRM_1675705962"], fields["title"])
        self.assertEqual(fields["UF_CRM_1651255181856"], 716)
        self.assertEqual(fields["UF_CRM_1774028164424"], 7262)
        self.assertEqual(fields["UF_CRM_1725892589"], 6890)
        self.assertIn("Incidente interno:", fields["comments"])
        calls = post.call_count
        _send_bitrix(delivery)
        self.assertEqual(post.call_count, calls)
        self.assertEqual(post.call_args_list[2].kwargs["json"]["useOriginalUfNames"], "Y")
        self.assertNotIn("stageId", fields)

    @patch("monitoring.deliveries.requests.post")
    @patch("monitoring.deliveries.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_bitrix_resolution_tracks_closure_and_reopening(self, getenv, post):
        monitor = Monitor.objects.create(name="Servidor", host="example.com")
        incident = Incident.objects.create(monitor=monitor, bitrix_deal_id="123")
        post.return_value.json.side_effect = [
            {"result": {"item": {"closed": "Y"}}},
            {"result": {"item": {"closed": "N"}}},
        ]
        sync_bitrix_resolutions()
        incident.refresh_from_db()
        self.assertEqual(incident.workflow_status, "Resuelto")
        Incident.objects.filter(pk=incident.pk).update(bitrix_synced_at=timezone.now() - timedelta(minutes=6))
        sync_bitrix_resolutions()
        incident.refresh_from_db()
        self.assertEqual(incident.workflow_status, "No reconocido")
        self.assertIsNone(incident.bitrix_resolved_at)

    @patch("monitoring.deliveries.os.getenv", return_value="https://example.bitrix24.com/rest/1/secret/")
    def test_bitrix_deal_link_omits_webhook_secret(self, getenv):
        self.assertEqual(bitrix_deal_url("123"), "https://example.bitrix24.com/crm/deal/details/123/")
        self.assertIsNone(bitrix_deal_url("123/?secret"))


class IncidentEmailTests(TenantTestCase):
    @patch("monitoring.deliveries.get_connection")
    @patch("monitoring.deliveries.send_mail", return_value=1)
    def test_email_variants_have_html_and_plain_text(self, send_mail_mock, get_connection_mock):
        from monitoring.deliveries import _send_email

        monitor = Monitor.objects.create(
            name="API <Interna>", kind=Monitor.Kind.HTTP, host="https://example.test/private",
            max_latency_ms=200, recipients="admin@example.test, guardia@example.test",
        )
        start = timezone.now() - timedelta(minutes=3)
        for kind, opened_title, recovered_title in (
            (Incident.Kind.SLOW, "Respuesta lenta", "Latencia normalizada"),
            (Incident.Kind.FAILURE, "Servicio caído", "Servicio recuperado"),
        ):
            with self.subTest(kind=kind):
                incident = Incident.objects.create(monitor=monitor, kind=kind, started_at=start)
                CheckResult.objects.create(
                    monitor=monitor, checked_at=start, status=CheckResult.Status.SLOW if kind == Incident.Kind.SLOW else CheckResult.Status.FAILURE,
                    latency_ms=360, http_status_code=503 if kind == Incident.Kind.FAILURE else 200,
                    detail="HTTP <503>" if kind == Incident.Kind.FAILURE else "Latencia alta",
                )
                opened = Delivery.objects.create(incident=incident, channel=Delivery.Channel.EMAIL, event="opened")
                _send_email(opened)
                args, kwargs = send_mail_mock.call_args
                self.assertIn(opened_title, args[0])
                self.assertEqual(args[3], ["admin@example.test", "guardia@example.test"])
                self.assertIn(opened_title, kwargs["html_message"])
                self.assertIn(opened_title, args[1])
                self.assertIn("360 ms", kwargs["html_message"])
                self.assertIn("&lt;Interna&gt;", kwargs["html_message"])
                self.assertNotIn("API <Interna>", kwargs["html_message"])
                self.assertIn("Ver incidente en Passing", kwargs["html_message"])
                self.assertNotIn("Duración", kwargs["html_message"])
                if kind == Incident.Kind.FAILURE:
                    self.assertIn("HTTP &lt;503&gt;", kwargs["html_message"])
                else:
                    self.assertIn("Umbral de latencia", kwargs["html_message"])

                recovery_at = start + timedelta(minutes=3)
                incident.recovered_at = recovery_at
                incident.save(update_fields=["recovered_at"])
                CheckResult.objects.create(monitor=monitor, checked_at=recovery_at, status=CheckResult.Status.OK, latency_ms=80, http_status_code=200)
                recovered = Delivery.objects.create(incident=incident, channel=Delivery.Channel.EMAIL, event="recovered")
                _send_email(recovered)
                args, kwargs = send_mail_mock.call_args
                self.assertIn(recovered_title, args[0])
                self.assertIn("Duración", kwargs["html_message"])
                self.assertIn("3 min", kwargs["html_message"])
                self.assertIn("80 ms", kwargs["html_message"])
                self.assertNotIn("HTTP &lt;503&gt;", kwargs["html_message"])
                start += timedelta(minutes=10)


class MonitorGroupTests(TenantTestCase):
    def test_group_form_normalizes_name_and_monitor_can_be_assigned(self):
        form = MonitorGroupForm(data={"name": "  Servicios   críticos  ", "description": "Producción", "sort_order": 1})
        self.assertTrue(form.is_valid(), form.errors)
        group = form.save()
        monitor = Monitor.objects.create(name="API", host="example.com", group=group)
        self.assertEqual(group.name, "Servicios críticos")
        self.assertEqual(monitor.group, group)

    def test_deleting_group_preserves_monitors_as_ungrouped(self):
        group = MonitorGroup.objects.create(name="Clientes")
        monitor = Monitor.objects.create(name="Portal", host="example.com", group=group)
        group.delete()
        monitor.refresh_from_db()
        self.assertIsNone(monitor.group)

    @patch("monitoring.views.render")
    def test_dashboard_builds_grouped_and_ungrouped_sections(self, render_mock):
        render_mock.return_value = HttpResponse("ok")
        group = MonitorGroup.objects.create(name="Infraestructura", sort_order=1)
        Monitor.objects.create(name="Servidor", host="server.example", group=group)
        Monitor.objects.create(name="Web", host="web.example")
        request = RequestFactory().get("/monitoring/")
        request.user = MagicMock(is_active=True, is_superuser=True)
        dashboard(request)
        context = render_mock.call_args.args[2]
        self.assertEqual([item["name"] for item in context["monitor_groups"]], ["Infraestructura", "Sin grupo"])
        self.assertEqual([item["monitors"][0].name for item in context["monitor_groups"]], ["Servidor", "Web"])
