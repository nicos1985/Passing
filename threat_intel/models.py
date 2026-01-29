
# threat_intel/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

class TechTag(models.Model):
    """
    Catálogo de tecnologías/activos a matchear (Ubuntu, MySQL, Laravel, React, AWS EC2, Cloudflare WAF, Fortinet, etc.)
    """
    name = models.CharField(max_length=80, unique=True)
    keywords = models.JSONField(default=list, blank=True)  # ["ubuntu", "jammy", "mysql", "laravel", ...]
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Source(models.Model):
    """
    Fuente de inteligencia (NVD, CISA, AWS bulletins, MSRC, etc.)
    """
    code = models.CharField(max_length=40, unique=True)  # "NVD", "CISA", "AWS", "MSRC"
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=30, default="api")  # api/rss/html
    base_url = models.URLField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class RawItem(models.Model):
    """
    Ítem crudo tal como viene de la fuente, para trazabilidad (sin perder evidencia).
    """
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    external_id = models.CharField(max_length=200)  # CVE-XXXX-YYYY o ID del advisory
    published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    url = models.URLField()
    title = models.CharField(max_length=500, blank=True)
    raw_payload = models.JSONField()  # respuesta API/RSS parseada o contenido normalizado

    class Meta:
        unique_together = [("source", "external_id")]

class IntelItem(models.Model):
    """
    Ítem normalizado (dedupe + enriquecimiento).
    """
    KIND_CHOICES = [
        ("cve", "CVE"),
        ("advisory", "Advisory"),
        ("bulletin", "Bulletin"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("unknown", "Unknown"),
    ]

    canonical_id = models.CharField(max_length=200, unique=True)  # preferir CVE si existe; si no, fuente:id
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other")

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    # Severidad estándar
    cvss = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="unknown")

    published_at = models.DateTimeField(null=True, blank=True)
    primary_url = models.URLField(blank=True)

    # Relevancia para su stack
    tech_tags = models.ManyToManyField(TechTag, blank=True)
    is_relevant = models.BooleanField(default=False)

    # Evidencia / referencias
    references = models.JSONField(default=list, blank=True)  # lista de URLs
    sources = models.ManyToManyField(Source, blank=True)     # de dónde se obtuvo

    created_at = models.DateTimeField(auto_now_add=True)

class Run(models.Model):
    """
    Una corrida mensual (o ad-hoc) de monitoreo.
    """
    RUN_TYPE = [("monthly", "Monthly"), ("adhoc", "Ad-hoc")]

    run_type = models.CharField(max_length=20, choices=RUN_TYPE, default="monthly")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    # métricas
    fetched_count = models.IntegerField(default=0)
    normalized_count = models.IntegerField(default=0)
    relevant_count = models.IntegerField(default=0)

    status = models.CharField(max_length=20, default="running")  # running/success/failed
    error = models.TextField(blank=True)

class RunItem(models.Model):
    """
    Relación entre corrida y los ítems detectados en ese periodo (para auditoría).
    """
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    item = models.ForeignKey(IntelItem, on_delete=models.CASCADE)
    detected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("run", "item")]

class AIAnalysis(models.Model):
    """
    Resultado del análisis IA sobre un IntelItem en el contexto de un Run (o general).
    """
    item = models.ForeignKey("IntelItem", on_delete=models.CASCADE)
    run = models.ForeignKey("Run", on_delete=models.CASCADE)

    summary_es = models.TextField()
    applies_to_stack = models.BooleanField(default=False)
    affected_tech = models.JSONField(default=list, blank=True)

    impact_previ = models.TextField()
    recommended_action = models.TextField()
    recommended_deadline = models.CharField(max_length=60, blank=True)

    priority = models.CharField(max_length=20, default="medium")  # critical/high/medium/low
    requires_management = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    model_name = models.CharField(max_length=80, default="gpt-4.1-mini")
    prompt_version = models.CharField(max_length=40, default="v1")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("item", "run")]


class Report(models.Model):
    """
    El informe mensual generado y enviado (contenido + evidencias).
    """
    run = models.OneToOneField(Run, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    body_md = models.TextField()       # o HTML si preferís
    body_html = models.TextField(blank=True)
    recipients = models.JSONField(default=list)  # ["rsi@..", "direccion@.."]
    sent_at = models.DateTimeField(null=True, blank=True)

class Review(models.Model):
    """
    Registro de revisión/decisión (RSI / Dirección).
    """
    DECISION = [
        ("approve_ticket", "Crear ticket"),
        ("monitor", "Monitorear"),
        ("not_applicable", "No aplica"),
        ("postpone", "Postergar"),
    ]

    item = models.ForeignKey(IntelItem, on_delete=models.CASCADE)
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    analysis = models.ForeignKey(AIAnalysis, on_delete=models.SET_NULL, null=True, blank=True)

    decision = models.CharField(max_length=30, choices=DECISION)
    notes = models.TextField(blank=True)

    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decided_at = models.DateTimeField(default=timezone.now)

    ticket_ref = models.CharField(max_length=200, blank=True)  # link/ID a Bitrix o sistema interno

class SourceState(models.Model):
    """
    Estado/cursor por fuente dentro de un tenant schema.
    Sirve para:
    - recordar el último run exitoso
    - guardar cursor de paginación/fecha (si la fuente lo requiere)
    """
    source = models.OneToOneField("Source", on_delete=models.CASCADE, related_name="state")
    last_successful_run_at = models.DateTimeField(null=True, blank=True)
    cursor = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.source.code} state"



