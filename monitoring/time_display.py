"""Per-user display timezone for monitoring pages and datetime forms."""

import re
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone


COOKIE_NAME = "monitoring_tz"
ZONE_PATTERN = re.compile(r"^[A-Za-z0-9_+\-/]{1,64}$")


def validated_zone(value):
    if not value or not ZONE_PATTERN.fullmatch(value) or ".." in value:
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return value


def monitoring_timezone(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        zone = validated_zone(request.COOKIES.get(COOKIE_NAME)) or settings.TIME_ZONE
        request.monitoring_timezone = zone
        with timezone.override(zone):
            return view(request, *args, **kwargs)
    return wrapped


def midnight_ticks(start, end, zone):
    """Calendar midnights in a display zone, including changes of UTC offset."""
    day = start.astimezone(zone).date()
    last_day = end.astimezone(zone).date()
    ticks = []
    while day <= last_day:
        midnight = datetime.combine(day, time.min, tzinfo=zone)
        # Some zones skip midnight when changing offset. Do not label 01:00 as 00:00.
        actual = midnight.astimezone(datetime_timezone.utc).astimezone(zone)
        if actual.date() == day and actual.time() == time.min and start <= midnight <= end:
            ticks.append({'at': midnight.isoformat(), 'label': midnight.strftime('%d/%m')})
        day += timedelta(days=1)
    return ticks
