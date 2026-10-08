"""Scheduled maintenance is evaluated in the application's local timezone."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import MaintenanceWindow


def _occurrence_start(window, day):
    local_zone = ZoneInfo(window.time_zone)
    local_start = timezone.localtime(window.starts_at, local_zone)
    return datetime.combine(day, local_start.timetz().replace(tzinfo=None), local_zone)


def window_active(window, at=None):
    if not window.enabled:
        return False
    at = at or timezone.now()
    if window.recurrence == MaintenanceWindow.Recurrence.ONCE:
        return window.starts_at <= at < window.ends_at
    local_zone = ZoneInfo(window.time_zone)
    local_at = timezone.localtime(at, local_zone)
    local_start = timezone.localtime(window.starts_at, local_zone)
    duration = window.ends_at - window.starts_at
    if duration <= timedelta(0):
        return False
    if window.recurrence == MaintenanceWindow.Recurrence.DAILY:
        days = (local_at.date(), local_at.date() - timedelta(days=1))
    else:
        offset = (local_at.weekday() - local_start.weekday()) % 7
        current_day = local_at.date() - timedelta(days=offset)
        days = (current_day, current_day - timedelta(days=7))
    return any(start >= window.starts_at and start <= at < start + duration for start in (_occurrence_start(window, day) for day in days))


def monitor_in_maintenance(monitor, at=None):
    at = at or timezone.now()
    if monitor.maintenance_until and monitor.maintenance_until > at:
        return True
    return any(window_active(window, at) for window in monitor.maintenance_windows.all())


def next_window_start(window, at=None):
    if not window.enabled:
        return None
    at = at or timezone.now()
    if window.recurrence == MaintenanceWindow.Recurrence.ONCE:
        return window.starts_at if window.starts_at > at else None
    local_zone = ZoneInfo(window.time_zone)
    local_at = timezone.localtime(at, local_zone)
    local_start = timezone.localtime(window.starts_at, local_zone)
    for offset in range(8):
        day = local_at.date() + timedelta(days=offset)
        if window.recurrence == MaintenanceWindow.Recurrence.WEEKLY and day.weekday() != local_start.weekday():
            continue
        candidate = _occurrence_start(window, day)
        if candidate >= window.starts_at and candidate > at:
            return candidate
    return None
