"""Per-user display timezone for monitoring pages and datetime forms."""

import re
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
