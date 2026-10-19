from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class MonitorGroup(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Monitor(models.Model):
    class Kind(models.TextChoices):
        PING = "ping", "Ping (ICMP)"
        HTTP = "http", "HTTP/HTTPS"
        TCP = "tcp", "Puerto TCP"
        TLS = "tls", "Certificado TLS"
        HEARTBEAT = "heartbeat", "Tarea programada"

    class State(models.TextChoices):
        UNKNOWN = "unknown", "Sin datos"
        UP = "up", "Saludable"
        SLOW = "slow", "Respuesta lenta"
        DOWN = "down", "Caído"

    group = models.ForeignKey(MonitorGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="monitors")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    host = models.CharField(max_length=500)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PING)
    interval_seconds = models.PositiveIntegerField(default=60, validators=[MinValueValidator(60), MaxValueValidator(3600)])
    timeout_seconds = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(30)])
    expected_http_codes = models.CharField(max_length=120, default="200-299")
    max_latency_ms = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(30000)])
    json_path = models.CharField(max_length=120, blank=True)
    json_expected_value = models.CharField(max_length=200, blank=True)
    tls_min_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(365)])
    heartbeat_interval_minutes = models.PositiveIntegerField(default=1440, validators=[MinValueValidator(1), MaxValueValidator(10080)])
    heartbeat_grace_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(0), MaxValueValidator(1440)])
    heartbeat_token_hash = models.CharField(max_length=64, blank=True)
    heartbeat_last_signal_at = models.DateTimeField(null=True, blank=True)
    failure_threshold = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    recovery_threshold = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(10)])
    recipients = models.TextField(blank=True, help_text="Correos separados por comas")
    enabled = models.BooleanField(default=True)
    maintenance_until = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=State.choices, default=State.UNKNOWN)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    consecutive_successes = models.PositiveSmallIntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    check_started_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=8, blank=True)
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    last_http_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_detail = models.CharField(max_length=240, blank=True)
    next_check_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        permissions = [("manage_monitoring", "Puede administrar monitorización")]

    def __str__(self):
        return self.name

    @property
    def recipients_list(self):
        return [address.strip() for address in self.recipients.split(",") if address.strip()]


class WorkerHeartbeat(models.Model):
    """One row per tenant, updated after each completed worker cycle."""

    last_cycle_at = models.DateTimeField(null=True, blank=True)
    alert_opened_at = models.DateTimeField(null=True, blank=True)
    alert_email_sent_at = models.DateTimeField(null=True, blank=True)
    alert_bitrix_deal_id = models.CharField(max_length=30, blank=True)


class MaintenanceWindow(models.Model):
    class Recurrence(models.TextChoices):
        ONCE = "once", "Una vez"
        DAILY = "daily", "Diariamente"
        WEEKLY = "weekly", "Semanalmente"

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="maintenance_windows")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    recurrence = models.CharField(max_length=8, choices=Recurrence.choices, default=Recurrence.ONCE)
    time_zone = models.CharField(max_length=64, default="UTC")
    note = models.CharField(max_length=160, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]


class DeploymentMarker(models.Model):
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="deployments")
    deployed_at = models.DateTimeField(default=timezone.now, db_index=True)
    version = models.CharField(max_length=80)
    note = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deployed_at"]
        constraints = [models.UniqueConstraint(fields=["monitor", "deployed_at", "version", "note"], name="monitoring_unique_deployment")]


class CheckResult(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "Correcto"
        SLOW = "slow", "Respuesta lenta"
        FAILURE = "failure", "Falla"
        ERROR = "error", "Error del monitor"

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="results")
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=8, choices=Status.choices)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    http_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    detail = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["monitor", "checked_at"])]


class HourlySummary(models.Model):
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="summaries")
    hour = models.DateTimeField()
    ok_count = models.PositiveIntegerField(default=0)
    latency_sum_ms = models.BigIntegerField(default=0)
    latency_count = models.PositiveIntegerField(default=0)
    latency_histogram = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["monitor", "hour"], name="monitoring_hour_unique")]


class Incident(models.Model):
    class Kind(models.TextChoices):
        FAILURE = "failure", "Falla"
        SLOW = "slow", "Respuesta lenta"

    class EndReason(models.TextChoices):
        RECOVERED = "recovered", "Recuperado"
        ESCALATED = "escalated", "Escaló a caída"
        SLOWED = "slowed", "Pasó a respuesta lenta"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.FAILURE)
    end_reason = models.CharField(max_length=12, choices=EndReason.choices, default=EndReason.RECOVERED)
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="incidents")
    started_at = models.DateTimeField(default=timezone.now)
    recovered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    bitrix_deal_id = models.CharField(max_length=30, blank=True)
    bitrix_error = models.CharField(max_length=240, blank=True)
    bitrix_resolved_at = models.DateTimeField(null=True, blank=True)
    bitrix_synced_at = models.DateTimeField(null=True, blank=True)
    bitrix_sync_error = models.CharField(max_length=240, blank=True)
    json_evidence_encrypted = models.TextField(blank=True)
    json_evidence_truncated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        constraints = [models.UniqueConstraint(fields=["monitor"], condition=models.Q(recovered_at__isnull=True), name="monitoring_one_open_incident")]

    @property
    def end_label(self):
        if self.end_reason == self.EndReason.ESCALATED:
            return "Escaló a caída"
        if self.end_reason == self.EndReason.SLOWED:
            return "Pasó a respuesta lenta"
        return "Latencia normalizada" if self.kind == self.Kind.SLOW else "Servicio recuperado"

    @property
    def workflow_status(self):
        if self.bitrix_resolved_at:
            return "Resuelto"
        if self.acknowledged_at:
            return "Reconocido"
        return "No reconocido"


class Delivery(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Correo"
        BITRIX = "bitrix", "Bitrix24"

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=12, choices=Channel.choices)
    event = models.CharField(max_length=12, choices=[("opened", "Apertura"), ("recovered", "Recuperación")])
    status = models.CharField(max_length=12, default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["incident", "channel", "event"], name="monitoring_delivery_unique")]
