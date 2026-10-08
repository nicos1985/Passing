"""Worker health shared by the dashboard and the independent watchdog."""

from datetime import timedelta

from django.utils import timezone

from .models import WorkerHeartbeat


STALE_AFTER = timedelta(minutes=3)


def worker_health(monitors, now=None):
    now = now or timezone.now()
    heartbeat = WorkerHeartbeat.objects.filter(pk=1).first()
    last_cycle_at = heartbeat.last_cycle_at if heartbeat else None
    recent = bool(last_cycle_at and last_cycle_at >= now - STALE_AFTER)
    active = [monitor for monitor in monitors if monitor.enabled]
    overdue = sum(
        monitor.next_check_at < now - timedelta(seconds=max(monitor.interval_seconds, 120))
        for monitor in active
    )
    if not active:
        label = "Sin monitoreos activos"
    elif not last_cycle_at:
        label = "Worker sin iniciar"
    elif not recent:
        label = "Worker sin actividad"
    elif overdue:
        label = f"Worker activo · {overdue} checks atrasados"
    else:
        label = "Worker activo"
    return {
        "worker_recent": recent,
        "worker_healthy": recent and not overdue,
        "worker_label": label,
        "last_cycle_at": last_cycle_at,
        "overdue_count": overdue,
        "active_count": len(active),
    }
