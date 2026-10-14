"""Availability trends from raw checks, hourly summaries and incidents."""

from datetime import timedelta, timezone as datetime_timezone

from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone

from .latency_stats import add_latency, merge_histograms, p95_upper_bound
from .models import CheckResult, HourlySummary, Incident


PERIODS = {1: (24, timedelta(hours=1)), 7: (7, timedelta(days=1)), 30: (30, timedelta(days=1)), 365: (53, timedelta(days=7))}


def _metrics(bucket):
    measured = bucket["ok"] + bucket["slow"] + bucket["failure"]
    latency_count = bucket["latency_count"]
    covered = sum(bucket["histogram"].values())
    return {
        "ok": bucket["ok"], "slow": bucket["slow"], "failure": bucket["failure"], "error": bucket["error"],
        "availability_pct": round(100 * (bucket["ok"] + bucket["slow"]) / measured, 2) if measured else None,
        "latency_avg_ms": round(bucket["latency_sum"] / latency_count) if latency_count else None,
        "latency_p95_ms": p95_upper_bound(bucket["histogram"]),
        "p95_coverage_pct": round(100 * covered / latency_count) if latency_count else None,
    }


def availability_history(monitor, days, now=None):
    now = now or timezone.now()
    count, step = PERIODS[days]
    if days == 1:
        current = now.replace(minute=0, second=0, microsecond=0)
    else:
        current = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = current - step * (count - 1)
    slots = []
    for index in range(count):
        slots.append({"start": start + step * index, "ok": 0, "slow": 0, "failure": 0, "error": 0,
                      "latency_sum": 0, "latency_count": 0, "histogram": {}})

    def slot_at(when):
        index = min(count - 1, max(0, int((when - start) // step)))
        return slots[index]

    for summary in HourlySummary.objects.filter(monitor=monitor, hour__gte=start, hour__lte=now).iterator():
        slot = slot_at(summary.hour)
        slot["ok"] += summary.ok_count
        slot["latency_sum"] += summary.latency_sum_ms
        slot["latency_count"] += summary.latency_count
        merge_histograms(slot["histogram"], summary.latency_histogram)

    for checked_at, latency in CheckResult.objects.filter(
        monitor=monitor, status=CheckResult.Status.OK, checked_at__gte=start, checked_at__lte=now,
    ).values_list("checked_at", "latency_ms").iterator():
        slot = slot_at(checked_at)
        slot["ok"] += 1
        if latency is not None:
            slot["latency_sum"] += latency
            slot["latency_count"] += 1
            add_latency(slot["histogram"], latency)

    truncation = TruncHour("checked_at", tzinfo=datetime_timezone.utc) if days == 1 else TruncDay("checked_at", tzinfo=datetime_timezone.utc)
    failed = CheckResult.objects.filter(
        monitor=monitor, status__in=[CheckResult.Status.SLOW, CheckResult.Status.FAILURE, CheckResult.Status.ERROR],
        checked_at__gte=start, checked_at__lte=now,
    ).annotate(period=truncation).values("period", "status").annotate(total=Count("pk"))
    for group in failed:
        slot_at(group["period"])[group["status"]] += group["total"]

    for checked_at, latency in CheckResult.objects.filter(
        monitor=monitor, status=CheckResult.Status.SLOW, checked_at__gte=start, checked_at__lte=now,
    ).values_list("checked_at", "latency_ms").iterator():
        slot = slot_at(checked_at)
        if latency is not None:
            slot["latency_sum"] += latency
            slot["latency_count"] += 1
            add_latency(slot["histogram"], latency)

    total = {"ok": 0, "slow": 0, "failure": 0, "error": 0, "latency_sum": 0, "latency_count": 0, "histogram": {}}
    for slot in slots:
        for key in ("ok", "slow", "failure", "error", "latency_sum", "latency_count"):
            total[key] += slot[key]
        merge_histograms(total["histogram"], slot["histogram"])

    incidents = Incident.objects.filter(monitor=monitor, started_at__lte=now).filter(
        Q(recovered_at__isnull=True) | Q(recovered_at__gt=start)
    ).order_by("-started_at")
    incident_count = 0
    downtime_seconds = 0
    recent_incidents = []
    for incident in incidents.iterator():
        end = min(incident.recovered_at or now, now)
        overlap = max(0, round((end - max(start, incident.started_at)).total_seconds()))
        if not overlap:
            continue
        incident_count += 1
        if incident.kind == Incident.Kind.FAILURE:
            downtime_seconds += overlap
        if len(recent_incidents) < 20:
            recent_incidents.append({
                "id": incident.pk, "kind": incident.kind, "started_at": incident.started_at.isoformat(),
                "recovered_at": incident.recovered_at.isoformat() if incident.recovered_at else None,
                "duration_seconds": max(0, round((end - incident.started_at).total_seconds())),
                "period_seconds": overlap,
            })

    return {
        "days": days, "start": start.isoformat(), "end": now.isoformat(),
        "totals": {**_metrics(total), "incident_count": incident_count, "downtime_seconds": downtime_seconds},
        "buckets": [{"start": slot["start"].isoformat(), **_metrics(slot)} for slot in slots],
        "incidents": recent_incidents,
    }
