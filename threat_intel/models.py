
# threat_intel/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class TechTag(models.Model):
    """
    Catálogo de tecnologías/activos a matchear (Ubuntu, MySQL, Laravel, React, AWS EC2, Cloudflare WAF, Fortinet, etc.)
    """
    name = models.CharField(max_length=80, unique=True, verbose_name=_('Nombre'))
    keywords = models.JSONField(default=list, blank=True, verbose_name=_('Palabras clave'))  # ["ubuntu", "jammy", "mysql", "laravel", ...]
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))

    def __str__(self):
        return self.name

class Source(models.Model):
    """
    Fuente de inteligencia (NVD, CISA, AWS bulletins, MSRC, etc.)
    """
    code = models.CharField(max_length=40, unique=True, verbose_name=_('Código'))  # "NVD", "CISA", "AWS", "MSRC"
    name = models.CharField(max_length=120, verbose_name=_('Nombre'))
    kind = models.CharField(max_length=30, default="api", verbose_name=_('Tipo'))  # api/rss/html
    base_url = models.URLField(verbose_name=_('URL base'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))

    def __str__(self):
        return self.name

class RawItem(models.Model):
    """
    Ítem crudo tal como viene de la fuente, para trazabilidad (sin perder evidencia).
    """
    source = models.ForeignKey(Source, on_delete=models.PROTECT, verbose_name=_('Fuente'))
    external_id = models.CharField(max_length=200, verbose_name=_('ID externo'))  # CVE-XXXX-YYYY o ID del advisory
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Fecha de publicación'))
    fetched_at = models.DateTimeField(default=timezone.now, verbose_name=_('Fecha de obtención'))
    url = models.URLField(verbose_name=_('URL'))
    title = models.CharField(max_length=500, blank=True, verbose_name=_('Título'))
    raw_payload = models.JSONField(verbose_name=_('Payload crudo'))  # respuesta API/RSS parseada o contenido normalizado

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

    canonical_id = models.CharField(max_length=200, unique=True, verbose_name=_('ID canónico'))  # preferir CVE si existe; si no, fuente:id
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other", verbose_name=_('Tipo'))

    title = models.CharField(max_length=500, verbose_name=_('Título'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))

    # Severidad estándar
    cvss = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, verbose_name=_('CVSS'))
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="unknown", verbose_name=_('Severidad'))

    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Fecha de publicación'))
    primary_url = models.URLField(blank=True, verbose_name=_('URL principal'))

    # Relevancia para su stack
    tech_tags = models.ManyToManyField(TechTag, blank=True, verbose_name=_('Etiquetas tecnológicas'))
    is_relevant = models.BooleanField(default=False, verbose_name=_('Es relevante'))

    # Evidencia / referencias
    references = models.JSONField(default=list, blank=True, verbose_name=_('Referencias'))  # lista de URLs
    sources = models.ManyToManyField(Source, blank=True, verbose_name=_('Fuentes'))     # de dónde se obtuvo

    created_at = models.DateTimeField(auto_now_add=True)

class Run(models.Model):
    """
    Una corrida mensual (o ad-hoc) de monitoreo.
    """
    RUN_TYPE = [("monthly", "Monthly"), ("adhoc", "Ad-hoc")]

    run_type = models.CharField(max_length=20, choices=RUN_TYPE, default="monthly", verbose_name=_('Tipo de corrida'))
    period_start = models.DateTimeField(verbose_name=_('Inicio del periodo'))
    period_end = models.DateTimeField(verbose_name=_('Fin del periodo'))
    started_at = models.DateTimeField(default=timezone.now, verbose_name=_('Inicio'))
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Fin'))

    # métricas
    fetched_count = models.IntegerField(default=0, verbose_name=_('Ítems obtenidos'))
    normalized_count = models.IntegerField(default=0, verbose_name=_('Ítems normalizados'))
    relevant_count = models.IntegerField(default=0, verbose_name=_('Ítems relevantes'))

    status = models.CharField(max_length=20, default="running", verbose_name=_('Estado'))  # running/success/failed
    error = models.TextField(blank=True, verbose_name=_('Error'))

class RunItem(models.Model):
    """
    Relación entre corrida y los ítems detectados en ese periodo (para auditoría).
    """
    run = models.ForeignKey(Run, on_delete=models.CASCADE, verbose_name=_('Corrida'))
    item = models.ForeignKey(IntelItem, on_delete=models.CASCADE, verbose_name=_('Ítem'))
    detected_at = models.DateTimeField(default=timezone.now, verbose_name=_('Fecha de detección'))

    class Meta:
        unique_together = [("run", "item")]

class AIAnalysis(models.Model):
    """
    Resultado del análisis IA sobre un IntelItem en el contexto de un Run (o general).
    """
    item = models.ForeignKey("IntelItem", on_delete=models.CASCADE, verbose_name=_('Ítem'))
    run = models.ForeignKey("Run", on_delete=models.CASCADE, verbose_name=_('Corrida'))

    summary_es = models.TextField(verbose_name=_('Resumen (ES)'))
    applies_to_stack = models.BooleanField(default=False, verbose_name=_('Aplica al stack'))
    affected_tech = models.JSONField(default=list, blank=True, verbose_name=_('Tecnologías afectadas'))

    impact_previ = models.TextField()
    recommended_action = models.TextField()
    recommended_deadline = models.CharField(max_length=60, blank=True, verbose_name=_('Fecha límite recomendada'))

    priority = models.CharField(max_length=20, default="medium", verbose_name=_('Prioridad'))  # critical/high/medium/low
    requires_management = models.BooleanField(default=False, verbose_name=_('Requiere gestión'))
    notes = models.TextField(blank=True, verbose_name=_('Notas'))

    model_name = models.CharField(max_length=80, default="gpt-4.1-mini", verbose_name=_('Nombre del modelo'))
    prompt_version = models.CharField(max_length=40, default="v1", verbose_name=_('Versión del prompt'))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("item", "run")]


class Report(models.Model):
    """
    El informe mensual generado y enviado (contenido + evidencias).
    """
    run = models.OneToOneField(Run, on_delete=models.CASCADE, verbose_name=_('Corrida'))
    subject = models.CharField(max_length=200, verbose_name=_('Asunto'))
    body_md = models.TextField(verbose_name=_('Cuerpo (MD)'))       # o HTML si preferís
    body_html = models.TextField(blank=True, verbose_name=_('Cuerpo (HTML)'))
    recipients = models.JSONField(default=list, verbose_name=_('Destinatarios'))  # ["rsi@..", "direccion@.."]
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Enviado en'))

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

    item = models.ForeignKey(IntelItem, on_delete=models.CASCADE, verbose_name=_('Ítem'))
    run = models.ForeignKey(Run, on_delete=models.CASCADE, verbose_name=_('Corrida'))
    analysis = models.ForeignKey(AIAnalysis, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Análisis'))

    decision = models.CharField(max_length=30, choices=DECISION, default="monitor", verbose_name=_('Decisión'))
    notes = models.TextField(blank=True, verbose_name=_('Notas'))

    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_('Decidido por'))
    decided_at = models.DateTimeField(default=timezone.now, verbose_name=_('Fecha de decisión'))

    ticket_ref = models.CharField(max_length=200, blank=True, verbose_name=_('Referencia del ticket'))  # link/ID a Bitrix o sistema interno


class IntelThreatLink(models.Model):
    """
    Enlace persistente entre un `IntelItem` detectado por threat_intel
    y una entrada del catálogo `resources.Threat`.

    Esto permite reutilizar el catálogo de `resources` al crear evaluaciones
    y mantener trazabilidad de qué ítems de inteligencia fueron mapeados.
    """
    MATCH_TYPE = [("auto", "Auto-match"), ("manual", "Manual")] 

    intel_item = models.ForeignKey("IntelItem", on_delete=models.CASCADE, related_name="threat_links")
    resources_threat = models.ForeignKey("resources.Threat", on_delete=models.CASCADE, related_name="intel_links")
    matched_at = models.DateTimeField(default=timezone.now)
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE, default="auto", verbose_name=_('Tipo de coincidencia'))
    confidence = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name=_('Confianza'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Creado por'))
    notes = models.TextField(blank=True, verbose_name=_('Notas'))

    class Meta:
        unique_together = [("intel_item", "resources_threat")]

    def __str__(self):
        return f"IntelItem {self.intel_item_id} -> Threat {self.resources_threat_id} ({self.match_type})"

class SourceState(models.Model):
    """
    Estado/cursor por fuente dentro de un tenant schema.
    Sirve para:
    - recordar el último run exitoso
    - guardar cursor de paginación/fecha (si la fuente lo requiere)
    """
    source = models.OneToOneField("Source", on_delete=models.CASCADE, related_name="state", verbose_name=_('Fuente'))
    last_successful_run_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Última corrida exitosa'))
    cursor = models.JSONField(default=dict, blank=True, verbose_name=_('Cursor'))  # p.ej. {"last_fetched_page": 3} o {"last_fetched_date": "2024-05-01T12:00:00Z"}

    def __str__(self):
        return f"{self.source.code} state"



