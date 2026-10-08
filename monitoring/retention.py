from datetime import timedelta

from django.db import transaction
from django.db.models.functions import TruncHour
from django.utils import timezone

from .models import CheckResult, DeploymentMarker, HourlySummary, Incident, MaintenanceWindow
from .latency_stats import add_latency, merge_histograms


def compact_history():
    now = timezone.now()
    cutoff = (now - timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    expiry = now - timedelta(days=365)
    # Each hour is aggregated and removed atomically to avoid losing OKs on interruption.
    hours = list(CheckResult.objects.filter(status=CheckResult.Status.OK, checked_at__lt=cutoff).annotate(hour=TruncHour("checked_at")).values_list("hour", flat=True).distinct().order_by("hour"))
    for hour in hours:
        with transaction.atomic():
            rows = CheckResult.objects.filter(status=CheckResult.Status.OK, checked_at__gte=hour, checked_at__lt=hour + timedelta(hours=1))
            groups = {}
            for monitor_id, latency in rows.values_list("monitor_id", "latency_ms").iterator():
                group = groups.setdefault(monitor_id, {"count": 0, "sum": 0, "latency_count": 0, "histogram": {}})
                group["count"] += 1
                if latency is not None:
                    group["sum"] += latency
                    group["latency_count"] += 1
                    add_latency(group["histogram"], latency)
            for monitor_id, group in groups.items():
                summary, _ = HourlySummary.objects.select_for_update().get_or_create(monitor_id=monitor_id, hour=hour)
                summary.ok_count += group["count"]
                summary.latency_sum_ms += group["sum"]
                summary.latency_count += group["latency_count"]
                histogram = summary.latency_histogram.copy()
                merge_histograms(histogram, group["histogram"])
                summary.latency_histogram = histogram
                summary.save()
            rows.delete()
    CheckResult.objects.filter(checked_at__lt=expiry).delete()
    HourlySummary.objects.filter(hour__lt=expiry).delete()
    Incident.objects.filter(recovered_at__lt=expiry).delete()
    DeploymentMarker.objects.filter(deployed_at__lt=expiry).delete()
    MaintenanceWindow.objects.filter(recurrence=MaintenanceWindow.Recurrence.ONCE, ends_at__lt=expiry).delete()
