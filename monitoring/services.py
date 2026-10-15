from datetime import timedelta
import hashlib
import hmac

from django.db import transaction
from django.utils import timezone

from .checks import run_check
from .evidence import encrypt_evidence
from .maintenance import monitor_in_maintenance
from .models import CheckResult, Delivery, Incident, Monitor
from supporthub.telegram_events import queue_monitoring_event


def _next_scheduled_check(scheduled_at, interval_seconds, finished_at):
    """Keep the configured cadence without replaying missed checks."""
    if scheduled_at > finished_at:
        return scheduled_at
    interval = timedelta(seconds=interval_seconds)
    elapsed_intervals = (finished_at - scheduled_at) // interval
    return scheduled_at + (elapsed_intervals + 1) * interval


def execute_monitor(monitor_id):
    monitor = Monitor.objects.get(pk=monitor_id)
    if not monitor.enabled:
        return None
    if monitor.kind == Monitor.Kind.HEARTBEAT:
        return evaluate_heartbeat(monitor_id)
    Monitor.objects.filter(pk=monitor_id, enabled=True).update(check_started_at=timezone.now())
    try:
        outcome = run_check(monitor)
        status, latency, detail = outcome[:3]
        http_status_code = outcome[3] if len(outcome) > 3 else None
        evidence = outcome[4] if len(outcome) > 4 else None
    except Exception:
        # A failed local probe must remain visible, without declaring the target down.
        status, latency, detail, http_status_code, evidence = CheckResult.Status.ERROR, None, "Error al ejecutar el check", None, None
    if status == CheckResult.Status.OK and monitor.max_latency_ms is not None and latency is not None and latency > monitor.max_latency_ms:
        status = CheckResult.Status.SLOW
        detail = f"Latencia {latency} ms supera {monitor.max_latency_ms} ms" + (f" ({detail})" if detail else "")
    return _save_result(monitor_id, status, latency, detail, http_status_code, evidence)


def record_heartbeat(monitor_id, token):
    with transaction.atomic():
        monitor = Monitor.objects.select_for_update().filter(pk=monitor_id).first()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if token and len(token) <= 256 else ""
        if not monitor or monitor.kind != Monitor.Kind.HEARTBEAT or not monitor.enabled or not token_hash or not monitor.heartbeat_token_hash or not hmac.compare_digest(token_hash, monitor.heartbeat_token_hash):
            return False
        _save_result(monitor_id, CheckResult.Status.OK, None, "Señal recibida", signal=True)
    return True


def evaluate_heartbeat(monitor_id):
    return _save_result(monitor_id, CheckResult.Status.FAILURE, None, "Señal no recibida dentro del plazo")


def _save_result(monitor_id, status, latency, detail, http_status_code=None, evidence=None, signal=False):
    now = timezone.now()
    with transaction.atomic():
        monitor = Monitor.objects.select_for_update().get(pk=monitor_id)
        if not monitor.enabled:
            monitor.check_started_at = None
            monitor.save(update_fields=["check_started_at"])
            return None
        if monitor.kind == Monitor.Kind.HEARTBEAT and not signal and monitor.next_check_at > now:
            return None
        previous_status = monitor.last_status
        result = CheckResult.objects.create(monitor=monitor, checked_at=now, status=status, latency_ms=latency, detail=detail, http_status_code=http_status_code)
        monitor.last_checked_at = now
        monitor.check_started_at = None
        monitor.last_status = status
        monitor.last_latency_ms = latency
        monitor.last_http_status_code = http_status_code
        monitor.last_detail = detail
        if monitor.kind == Monitor.Kind.HEARTBEAT:
            if signal:
                monitor.heartbeat_last_signal_at = now
            monitor.next_check_at = now + timedelta(minutes=monitor.heartbeat_interval_minutes + (monitor.heartbeat_grace_minutes if signal else 0))
        else:
            monitor.next_check_at = _next_scheduled_check(monitor.next_check_at, monitor.interval_seconds, now)
        in_maintenance = monitor_in_maintenance(monitor, now)
        if status == CheckResult.Status.OK:
            monitor.consecutive_successes += 1
            monitor.consecutive_failures = 0
            if monitor.state in (Monitor.State.DOWN, Monitor.State.SLOW) and monitor.consecutive_successes >= monitor.recovery_threshold:
                monitor.state = Monitor.State.UP
                incident = Incident.objects.filter(monitor=monitor, recovered_at__isnull=True).first()
                if incident:
                    incident.recovered_at = now
                    incident.save(update_fields=["recovered_at"])
                    if not in_maintenance and monitor.recipients_list:
                        Delivery.objects.get_or_create(incident=incident, channel=Delivery.Channel.EMAIL, event="recovered")
                    if not in_maintenance:
                        queue_monitoring_event(incident.pk, "recovered")
            elif monitor.state == Monitor.State.UNKNOWN:
                monitor.state = Monitor.State.UP
        elif status in (CheckResult.Status.FAILURE, CheckResult.Status.SLOW):
            target_state = Monitor.State.SLOW if status == CheckResult.Status.SLOW else Monitor.State.DOWN
            monitor.consecutive_failures = monitor.consecutive_failures + 1 if previous_status == status else 1
            monitor.consecutive_successes = 0
            incident = None
            if monitor.state != target_state and monitor.consecutive_failures >= monitor.failure_threshold:
                previous_incident = Incident.objects.filter(monitor=monitor, recovered_at__isnull=True).first()
                if previous_incident:
                    previous_incident.recovered_at = now
                    previous_incident.end_reason = (
                        Incident.EndReason.ESCALATED if target_state == Monitor.State.DOWN
                        else Incident.EndReason.SLOWED
                    )
                    previous_incident.save(update_fields=["recovered_at", "end_reason"])
                monitor.state = target_state
                incident = Incident.objects.create(
                    monitor=monitor, started_at=now,
                    kind=Incident.Kind.SLOW if status == CheckResult.Status.SLOW else Incident.Kind.FAILURE,
                )
                if not in_maintenance:
                    if monitor.recipients_list:
                        Delivery.objects.get_or_create(incident=incident, channel=Delivery.Channel.EMAIL, event="opened")
                    Delivery.objects.get_or_create(incident=incident, channel=Delivery.Channel.BITRIX, event="opened")
                    queue_monitoring_event(incident.pk, "opened")
            elif monitor.state == target_state:
                incident = Incident.objects.filter(monitor=monitor, recovered_at__isnull=True).first()
            if evidence and incident and not incident.json_evidence_encrypted:
                incident.json_evidence_encrypted = encrypt_evidence(evidence[0])
                incident.json_evidence_truncated = evidence[1]
                incident.save(update_fields=["json_evidence_encrypted", "json_evidence_truncated"])
        # An error in the local probe is not evidence of a remote outage.
        monitor.save()
    return result
