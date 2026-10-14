from datetime import datetime, timedelta, timezone as datetime_timezone
import hashlib
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import DeploymentMarkerForm, MaintenanceWindowForm, MonitorForm
from .evidence import decrypt_evidence
from .availability import PERIODS, availability_history
from .deliveries import bitrix_deal_url, delivery_error_message, send_test_email, test_bitrix_connection, test_smtp_connection
from .models import CheckResult, Delivery, DeploymentMarker, Incident, MaintenanceWindow, Monitor
from .maintenance import monitor_in_maintenance, next_window_start
from .services import record_heartbeat
from .time_display import COOKIE_NAME, monitoring_timezone, validated_zone
from .worker_health import worker_health


def _authorized(user, action='read'):
    return user.is_active and (
        user.is_superuser or user.has_perm('monitoring.manage_monitoring')
        or user.has_perm(f'monitoring.{action}_monitoring')
    )


def _monitor_live_state(monitor, now):
    running = bool(monitor.check_started_at and (now - monitor.check_started_at).total_seconds() <= monitor.timeout_seconds + 5)
    heartbeat = monitor.kind == Monitor.Kind.HEARTBEAT
    stale = bool(monitor.enabled and not heartbeat and not running and (not monitor.last_checked_at or monitor.last_checked_at < now - timedelta(seconds=max(monitor.interval_seconds * 2, 120))))
    maintenance = monitor_in_maintenance(monitor, now)
    if not monitor.enabled:
        label, badge = "Detenido", "secondary"
    elif running:
        label, badge = "Comprobando", "primary"
    elif maintenance:
        label, badge = "Mantenimiento", "info"
    elif stale:
        label, badge = "Sin datos recientes", "warning"
    elif heartbeat and monitor.state == Monitor.State.UNKNOWN:
        label, badge = "Esperando señal", "secondary"
    elif monitor.last_status == "error":
        label, badge = "Error del monitor", "warning"
    elif monitor.state == Monitor.State.UP:
        label, badge = "Saludable", "success"
    elif monitor.state == Monitor.State.DOWN:
        label, badge = "Caído", "danger"
    else:
        label, badge = "Sin datos", "secondary"
    return {"running": running, "stale": stale, "maintenance": maintenance, "manual_maintenance": bool(monitor.maintenance_until and monitor.maintenance_until > now), "label": label, "badge": badge}


@login_required
@monitoring_timezone
def dashboard(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    monitors = list(Monitor.objects.prefetch_related("maintenance_windows"))
    now = timezone.now()
    for monitor in monitors:
        live = _monitor_live_state(monitor, now)
        monitor.live_label = live["label"]
        monitor.live_badge = live["badge"]
        monitor.running = live["running"]
        monitor.in_maintenance = live["maintenance"]
        monitor.manual_maintenance = live["manual_maintenance"]
    health = worker_health(monitors, now)
    open_incidents = Incident.objects.filter(recovered_at__isnull=True)
    incidents = list(open_incidents.select_related("monitor")[:20])
    return render(request, "monitoring/dashboard.html", {"monitors": monitors, "incidents": incidents, "incident_count": open_incidents.count(), "healthy_count": sum(monitor.enabled and monitor.live_badge == "success" for monitor in monitors), "attention_count": sum(monitor.enabled and monitor.live_badge in {"danger", "warning", "secondary"} for monitor in monitors), "worker_label": health["worker_label"], "worker_healthy": health["worker_healthy"], "last_cycle_at": health["last_cycle_at"], "overdue_count": health["overdue_count"], "now": now, "can_create": _authorized(request.user, 'create'), "can_edit": _authorized(request.user, 'edit'), "can_delete": _authorized(request.user, 'delete')})


@login_required
@never_cache
@monitoring_timezone
def incident_list(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    state = request.GET.get("estado", "todos")
    if state not in {"todos", "activos", "recuperados", "resueltos", "pendientes"}:
        state = "todos"
    query = request.GET.get("q", "").strip()[:120]
    incidents = Incident.objects.select_related("monitor", "acknowledged_by").order_by("-started_at")
    if state == "activos":
        incidents = incidents.filter(recovered_at__isnull=True)
    elif state == "recuperados":
        incidents = incidents.filter(recovered_at__isnull=False)
    elif state == "resueltos":
        incidents = incidents.filter(bitrix_resolved_at__isnull=False)
    elif state == "pendientes":
        incidents = incidents.filter(bitrix_resolved_at__isnull=True)
    if query:
        incidents = incidents.filter(monitor__name__icontains=query)
    page = Paginator(incidents, 25).get_page(request.GET.get("pagina"))
    return render(request, "monitoring/incident_list.html", {"page": page, "state": state, "query": query})


@login_required
def information(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    return render(request, "monitoring/information.html")


@login_required
@never_cache
def live_status(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    now = timezone.now()
    monitors = []
    all_monitors = list(Monitor.objects.prefetch_related("maintenance_windows"))
    health = worker_health(all_monitors, now)
    for monitor in all_monitors:
        live = _monitor_live_state(monitor, now)
        monitors.append({
            "id": monitor.pk,
            "label": live["label"],
            "badge": live["badge"],
            "running": live["running"],
            "maintenance": live["maintenance"],
            "manual_maintenance": live["manual_maintenance"],
            "enabled": monitor.enabled,
            "interval_seconds": monitor.interval_seconds,
            "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
            "last_latency_ms": monitor.last_latency_ms,
            "last_http_status_code": monitor.last_http_status_code,
            "last_detail": monitor.last_detail,
            "next_check_at": monitor.next_check_at.isoformat(),
        })
    recent = [
        {"id": result.pk, "monitor": result.monitor.name, "status": result.get_status_display(), "status_code": result.status, "http_status_code": result.http_status_code, "detail": result.detail, "checked_at": result.checked_at.isoformat(), "latency_ms": result.latency_ms}
        for result in CheckResult.objects.select_related("monitor").order_by("-checked_at")[:10]
    ]
    open_incidents = Incident.objects.filter(recovered_at__isnull=True)
    incidents = [
        {"monitor": incident.monitor.name, "host": incident.monitor.host, "started_at": incident.started_at.isoformat(), "url": reverse("monitoring:incident", args=[incident.pk]), "workflow_status": incident.workflow_status}
        for incident in open_incidents.select_related("monitor").order_by("-started_at")[:20]
    ]
    return JsonResponse({"server_time": now.isoformat(), "monitors": monitors, "recent": recent, "incidents": incidents, "incident_count": open_incidents.count(), "worker_label": health["worker_label"], "worker_healthy": health["worker_healthy"], "last_cycle_at": health["last_cycle_at"].isoformat() if health["last_cycle_at"] else None, "overdue_count": health["overdue_count"]})


@login_required
@never_cache
def hourly_history(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    now = timezone.now()
    current_minute = int(now.timestamp() // 60)
    first_minute = current_minute - 59
    monitor_ids = list(Monitor.objects.values_list("pk", flat=True))
    slots = {monitor_id: [None] * 60 for monitor_id in monitor_ids}
    priority = {CheckResult.Status.OK: 1, CheckResult.Status.FAILURE: 2, CheckResult.Status.ERROR: 2}
    results = CheckResult.objects.filter(
        monitor_id__in=monitor_ids,
        checked_at__gte=datetime.fromtimestamp(first_minute * 60, tz=datetime_timezone.utc),
        checked_at__lte=now,
    ).values_list("monitor_id", "checked_at", "status", "latency_ms", "http_status_code", "detail")
    for monitor_id, checked_at, status, latency_ms, http_status_code, detail in results:
        index = int(checked_at.timestamp() // 60) - first_minute
        if not 0 <= index < 60:
            continue
        previous = slots[monitor_id][index]
        if previous is None or priority[status] >= priority[previous["status"]]:
            slots[monitor_id][index] = {"status": status, "checked_at": checked_at.isoformat(), "latency_ms": latency_ms, "http_status_code": http_status_code, "detail": detail}
    return JsonResponse({"server_time": now.isoformat(), "first_minute": first_minute, "histories": [{"id": monitor_id, "slots": slots[monitor_id]} for monitor_id in monitor_ids]})


@login_required
@monitoring_timezone
def monitor_detail(request, pk):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk)
    live = _monitor_live_state(monitor, timezone.now())
    return render(request, "monitoring/monitor_detail.html", {
        "monitor": monitor,
        "live": live,
        "can_create": _authorized(request.user, 'create'),
        "can_edit": _authorized(request.user, 'edit'),
        "can_delete": _authorized(request.user, 'delete'),
        "incidents": Incident.objects.filter(monitor=monitor).order_by("-started_at")[:10],
        "deployments": monitor.deployments.all()[:20],
        "maintenance_windows": monitor.maintenance_windows.all(),
    })


@login_required
@never_cache
def monitor_detail_data(request, pk):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk)
    hours = {"1": 1, "6": 6, "24": 24, "168": 168}.get(request.GET.get("hours", "24"))
    if hours is None:
        return JsonResponse({"error": "Período inválido"}, status=400)
    now = timezone.now()
    first_minute = int(now.timestamp() // 60) - 59
    slots = [None] * 60
    priority = {CheckResult.Status.OK: 1, CheckResult.Status.FAILURE: 2, CheckResult.Status.ERROR: 2}
    recent_hour = CheckResult.objects.filter(
        monitor=monitor,
        checked_at__gte=datetime.fromtimestamp(first_minute * 60, tz=datetime_timezone.utc),
        checked_at__lte=now,
    ).values_list("checked_at", "status", "latency_ms", "http_status_code", "detail")
    for checked_at, status, latency_ms, http_status_code, detail in recent_hour:
        index = int(checked_at.timestamp() // 60) - first_minute
        if 0 <= index < 60 and (slots[index] is None or priority[status] >= priority[slots[index]["status"]]):
            slots[index] = {"status": status, "checked_at": checked_at.isoformat(), "latency_ms": latency_ms, "http_status_code": http_status_code, "detail": detail}
    results = list(CheckResult.objects.filter(
        monitor=monitor, checked_at__gte=now - timedelta(hours=hours), checked_at__lte=now,
    ).order_by("checked_at").values_list("checked_at", "status", "latency_ms", "http_status_code", "detail"))
    latest = list(CheckResult.objects.filter(monitor=monitor).order_by("-checked_at").values_list(
        "checked_at", "status", "latency_ms", "detail", "http_status_code")[:30])
    live = _monitor_live_state(monitor, now)
    return JsonResponse({
        "server_time": now.isoformat(),
        "state": live["label"], "badge": live["badge"], "enabled": monitor.enabled,
        "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
        "last_latency_ms": monitor.last_latency_ms,
        "last_http_status_code": monitor.last_http_status_code, "last_detail": monitor.last_detail,
        "first_minute": first_minute, "slots": slots,
        "latencies": [{"checked_at": checked_at.isoformat(), "status": status, "latency_ms": latency_ms, "http_status_code": http_status_code, "detail": detail}
                      for checked_at, status, latency_ms, http_status_code, detail in results],
        "deployments": [{"deployed_at": marker.deployed_at.isoformat(), "version": marker.version, "note": marker.note}
                        for marker in monitor.deployments.filter(deployed_at__gte=now - timedelta(hours=hours), deployed_at__lte=now)[:100]],
        "recent": [{"checked_at": checked_at.isoformat(), "status": status, "latency_ms": latency_ms, "detail": detail, "http_status_code": http_status_code}
                   for checked_at, status, latency_ms, detail, http_status_code in latest],
    })


@login_required
@never_cache
def monitor_availability_data(request, pk):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk)
    try:
        days = int(request.GET.get("days", "1"))
    except (ValueError, TypeError):
        days = None
    if days not in PERIODS:
        return JsonResponse({"error": "Período inválido"}, status=400)
    return JsonResponse(availability_history(monitor, days))


@login_required
@monitoring_timezone
def monitor_form(request, pk=None):
    if not _authorized(request.user, 'edit' if pk else 'create'):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk) if pk else None
    previous_kind = monitor.kind if monitor else None
    form = MonitorForm(request.POST or None, instance=monitor)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        new_heartbeat = saved.kind == Monitor.Kind.HEARTBEAT and (previous_kind != Monitor.Kind.HEARTBEAT or not saved.heartbeat_token_hash)
        token = None
        if new_heartbeat:
            token = secrets.token_urlsafe(32)
            saved.heartbeat_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if saved.kind == Monitor.Kind.HEARTBEAT:
            if new_heartbeat or {"heartbeat_interval_minutes", "heartbeat_grace_minutes"} & set(form.changed_data):
                saved.next_check_at = timezone.now() + timedelta(minutes=saved.heartbeat_interval_minutes + saved.heartbeat_grace_minutes)
        elif not pk or "interval_seconds" in form.changed_data or previous_kind == Monitor.Kind.HEARTBEAT:
            saved.next_check_at = timezone.now()
        saved.save()
        if token:
            return _heartbeat_token_page(request, saved, token)
        messages.success(request, "Monitoreo guardado.")
        return redirect("monitoring:dashboard")
    return render(request, "monitoring/monitor_form.html", {"form": form, "monitor": monitor})


def _heartbeat_token_page(request, monitor, token):
    response = render(request, "monitoring/heartbeat_token.html", {"monitor": monitor, "token": token, "signal_url": request.build_absolute_uri(reverse("monitoring:heartbeat_signal", args=[monitor.pk]))})
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
@never_cache
def regenerate_heartbeat_token(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    with transaction.atomic():
        monitor = get_object_or_404(Monitor.objects.select_for_update(), pk=pk, kind=Monitor.Kind.HEARTBEAT)
        token = secrets.token_urlsafe(32)
        monitor.heartbeat_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        monitor.save(update_fields=["heartbeat_token_hash", "updated_at"])
    return _heartbeat_token_page(request, monitor, token)


@csrf_exempt
@require_POST
@never_cache
def heartbeat_signal(request, pk):
    token = request.headers.get("X-Monitoring-Token", "")
    if not record_heartbeat(pk, token):
        return HttpResponse(status=403)
    return HttpResponse(status=204)


@login_required
@never_cache
@monitoring_timezone
def status_page(request):
    now = timezone.now()
    monitors = list(Monitor.objects.prefetch_related("maintenance_windows").only("id", "name", "kind", "enabled", "state", "last_status", "last_checked_at", "check_started_at", "timeout_seconds", "interval_seconds", "maintenance_until", "next_check_at"))
    for monitor in monitors:
        monitor.live = _monitor_live_state(monitor, now)
    response = render(request, "monitoring/status.html", {"monitors": monitors, "updated_at": now})
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def set_display_timezone(request):
    zone = validated_zone(request.POST.get("timezone", ""))
    if not zone:
        return HttpResponseForbidden("Zona horaria inválida")
    destination = request.POST.get("next", reverse("monitoring:dashboard"))
    if not destination.startswith("/") or destination.startswith("//") or not url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        destination = reverse("monitoring:dashboard")
    response = redirect(destination)
    response.set_cookie(COOKIE_NAME, zone, max_age=365 * 86400, secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite="Lax")
    return response


@login_required
@never_cache
@monitoring_timezone
def maintenance_windows(request):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    now = timezone.now()
    windows = list(MaintenanceWindow.objects.select_related("monitor").order_by("monitor__name", "starts_at"))
    for window in windows:
        window.next_start = next_window_start(window, now)
    return render(request, "monitoring/maintenance_windows.html", {"windows": windows, "can_create": _authorized(request.user, 'create'), "can_edit": _authorized(request.user, 'edit'), "can_delete": _authorized(request.user, 'delete')})


@login_required
@require_http_methods(["GET", "POST"])
@monitoring_timezone
def maintenance_window_form(request, pk=None):
    if not _authorized(request.user, 'edit' if pk else 'create'):
        return HttpResponseForbidden()
    window = get_object_or_404(MaintenanceWindow, pk=pk) if pk else None
    form = MaintenanceWindowForm(request.POST or None, instance=window, initial={"monitor": request.GET.get("monitor")})
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.time_zone = request.monitoring_timezone
        saved.save()
        messages.success(request, "Ventana de mantenimiento guardada.")
        return redirect("monitoring:maintenance_windows")
    return render(request, "monitoring/maintenance_window_form.html", {"form": form, "window": window})


@login_required
@require_POST
def maintenance_window_delete(request, pk):
    if not _authorized(request.user, 'delete'):
        return HttpResponseForbidden()
    get_object_or_404(MaintenanceWindow, pk=pk).delete()
    messages.success(request, "Ventana eliminada.")
    return redirect("monitoring:maintenance_windows")


@login_required
@require_http_methods(["GET", "POST"])
@monitoring_timezone
def deployment_form(request, pk, marker_pk=None):
    if not _authorized(request.user, 'edit' if marker_pk else 'create'):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk)
    marker_instance = get_object_or_404(DeploymentMarker, pk=marker_pk, monitor=monitor) if marker_pk else None
    form = DeploymentMarkerForm(request.POST or None, instance=marker_instance, initial={"deployed_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
    if request.method == "POST" and form.is_valid():
        marker = form.save(commit=False)
        marker.monitor = monitor
        duplicate = DeploymentMarker.objects.filter(monitor=monitor, deployed_at=marker.deployed_at, version=marker.version, note=marker.note).exclude(pk=marker.pk).exists()
        if duplicate:
            form.add_error(None, "Ya existe ese despliegue para esta fecha y hora.")
        else:
            try:
                if marker_instance:
                    marker.save()
                    messages.success(request, "Despliegue actualizado.")
                else:
                    _, created = DeploymentMarker.objects.get_or_create(monitor=monitor, deployed_at=marker.deployed_at, version=marker.version, note=marker.note, defaults={"created_by": request.user})
                    messages.success(request, "Despliegue registrado." if created else "Ese despliegue ya estaba registrado.")
            except IntegrityError:
                form.add_error(None, "Ya existe ese despliegue para esta fecha y hora.")
            else:
                return redirect("monitoring:detail", pk=pk)
    return render(request, "monitoring/deployment_form.html", {"form": form, "monitor": monitor, "marker": marker_instance})


@login_required
@require_POST
def deployment_delete(request, pk, marker_pk):
    if not _authorized(request.user, 'delete'):
        return HttpResponseForbidden()
    get_object_or_404(DeploymentMarker, pk=marker_pk, monitor_id=pk).delete()
    messages.success(request, "Marca de despliegue eliminada.")
    return redirect("monitoring:detail", pk=pk)


@login_required
@require_POST
def acknowledge(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    incident = get_object_or_404(Incident, pk=pk)
    if not incident.acknowledged_at:
        incident.acknowledged_at = timezone.now()
        incident.acknowledged_by = request.user
        incident.save(update_fields=["acknowledged_at", "acknowledged_by"])
    return redirect("monitoring:incident", pk=incident.pk)


@login_required
@require_POST
def maintenance(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    monitor = get_object_or_404(Monitor, pk=pk)
    hours = request.POST.get("hours", "0")
    if hours not in {"0", "1", "4", "24"}:
        messages.error(request, "Período de mantenimiento inválido.")
    else:
        monitor.maintenance_until = timezone.now() + timedelta(hours=int(hours)) if hours != "0" else None
        monitor.save(update_fields=["maintenance_until", "updated_at"])
    return redirect("monitoring:dashboard")


@login_required
@require_POST
def toggle_active(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    with transaction.atomic():
        monitor = get_object_or_404(Monitor.objects.select_for_update(), pk=pk)
        monitor.enabled = not monitor.enabled
        if monitor.enabled:
            monitor.next_check_at = timezone.now() + timedelta(minutes=monitor.heartbeat_interval_minutes + monitor.heartbeat_grace_minutes) if monitor.kind == Monitor.Kind.HEARTBEAT else timezone.now()
            monitor.consecutive_failures = 0
            monitor.consecutive_successes = 0
            if not Incident.objects.filter(monitor=monitor, recovered_at__isnull=True).exists():
                monitor.state = Monitor.State.UNKNOWN
                monitor.last_status = ""
        else:
            monitor.check_started_at = None
        monitor.save()
    messages.success(request, f"Monitoreo {'iniciado' if monitor.enabled else 'detenido'}.")
    return redirect("monitoring:dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def delete_monitor(request, pk):
    if not _authorized(request.user, 'delete'):
        return HttpResponseForbidden()
    if request.method == "POST":
        with transaction.atomic():
            monitor = get_object_or_404(Monitor.objects.select_for_update(), pk=pk)
            name = monitor.name
            monitor.delete()
        messages.success(request, f"Monitoreo {name} eliminado.")
        return redirect("monitoring:dashboard")
    monitor = get_object_or_404(Monitor, pk=pk)
    return render(request, "monitoring/monitor_confirm_delete.html", {
        "monitor": monitor,
        "check_count": monitor.results.count(),
        "incident_count": monitor.incidents.count(),
    })


@login_required
@never_cache
@monitoring_timezone
def incident_detail(request, pk):
    if not _authorized(request.user):
        return HttpResponseForbidden()
    incident = get_object_or_404(Incident.objects.select_related("monitor", "acknowledged_by"), pk=pk)
    results = CheckResult.objects.filter(monitor=incident.monitor, checked_at__gte=incident.started_at).order_by("-checked_at")[:100]
    opening_result = CheckResult.objects.filter(monitor=incident.monitor, checked_at__gte=incident.started_at).order_by("checked_at").first()
    deliveries = list(incident.deliveries.order_by("created_at"))
    for delivery in deliveries:
        delivery.error_display = delivery_error_message(delivery.last_error, delivery.channel) if delivery.last_error else ""
    test_email_default = request.user.email or (incident.monitor.recipients_list[0] if incident.monitor.recipients_list else "")
    can_edit = _authorized(request.user, 'edit')
    return render(request, "monitoring/incident_detail.html", {"incident": incident, "opening_result": opening_result, "results": results, "deliveries": deliveries, "test_email_default": test_email_default if can_edit else "", "bitrix_deal_url": bitrix_deal_url(incident.bitrix_deal_id) if incident.bitrix_deal_id else None, "json_evidence": decrypt_evidence(incident.json_evidence_encrypted) if can_edit else None, "can_edit": can_edit})


@login_required
@require_POST
def retry_delivery(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    with transaction.atomic():
        delivery = get_object_or_404(Delivery.objects.select_for_update(), pk=pk)
        if delivery.status in {"pending", "failed"}:
            if delivery.status == "failed":
                delivery.attempts = 0
            delivery.status = "pending"
            delivery.next_attempt_at = timezone.now()
            delivery.save(update_fields=["attempts", "status", "next_attempt_at"])
            messages.success(request, "Reintento programado para el próximo ciclo del worker.")
        else:
            messages.info(request, "Este envío ya fue procesado o está en curso.")
    return redirect("monitoring:incident", pk=delivery.incident_id)


@login_required
@require_POST
def test_notification_connection(request, pk, channel):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    get_object_or_404(Incident, pk=pk)
    if channel not in {Delivery.Channel.EMAIL, Delivery.Channel.BITRIX}:
        return HttpResponseForbidden()
    try:
        if channel == Delivery.Channel.EMAIL:
            test_smtp_connection()
        else:
            test_bitrix_connection()
    except Exception as exc:
        messages.error(request, delivery_error_message(exc, channel))
    else:
        if channel == Delivery.Channel.EMAIL:
            messages.success(request, "Autenticación SMTP correcta. No se envió ningún correo.")
        else:
            messages.success(request, "Bitrix24 respondió y se encontró la opción Crítica. Esta prueba no crea negociaciones ni comprueba el permiso de creación.")
    return redirect("monitoring:incident", pk=pk)


@login_required
@require_POST
def test_email_delivery(request, pk):
    if not _authorized(request.user, 'edit'):
        return HttpResponseForbidden()
    incident = get_object_or_404(Incident.objects.select_related("monitor"), pk=pk)
    address = request.POST.get("email", "").strip()
    allowed = {item.lower() for item in incident.monitor.recipients_list}
    if request.user.email:
        allowed.add(request.user.email.lower())
    try:
        validate_email(address)
    except ValidationError:
        messages.error(request, "Ingresá un correo válido.")
    else:
        if address.lower() not in allowed:
            messages.error(request, "Usá tu correo de usuario o un destinatario configurado en este monitoreo.")
        else:
            try:
                send_test_email(address)
            except Exception as exc:
                messages.error(request, delivery_error_message(exc, Delivery.Channel.EMAIL))
            else:
                messages.success(request, f"El servidor SMTP aceptó el correo de prueba para {address}.")
    return redirect("monitoring:incident", pk=pk)
