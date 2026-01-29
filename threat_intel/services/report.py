# threat_intel/services/report.py
from __future__ import annotations
from django.conf import settings
from django.utils import timezone
from threat_intel.models import Run, RunItem, IntelItem
from threat_intel.models import AIAnalysis


def build_report_for_run(run):
    # 1) Inicialización SIEMPRE
    lines = []

    period_txt = f"{run.period_start.date()} a {run.period_end.date()}"
    subject = f"[Threat Intel] Informe mensual {period_txt}"

    lines.append(f"# Informe de Amenazas y Vulnerabilidades ({period_txt})")
    lines.append("")
    lines.append(f"- Tenant/Schema: **{getattr(run, 'schema_name', '') or getattr(run, 'tenant_schema', '') or 'N/A'}**")
    lines.append(f"- Ejecutado: {timezone.localtime(run.started_at).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 2) Base queryset (relevantes del run)
    items_qs = (
        IntelItem.objects
        .filter(runitem__run=run, is_relevant=True)
        .distinct()
    )

    critical_count = items_qs.filter(severity="critical").count()
    high_count = items_qs.filter(severity="high").count()
    medium_count = items_qs.filter(severity="medium").count()
    unknown_count = items_qs.filter(severity="unknown").count()

    lines.append("## Resumen")
    lines.append(f"- Relevantes totales: **{items_qs.count()}**")
    lines.append(f"- Severidad: críticos={critical_count}, altos={high_count}, medios={medium_count}, desconocidos={unknown_count}")
    lines.append("")

    # 3) Top priorizadas (critical/high + medium top 10)
    critical_high = items_qs.filter(severity__in=["critical", "high"]).order_by("-cvss", "severity")
    medium_top10 = items_qs.filter(severity="medium").order_by("-cvss")[:10]

    top = list(critical_high) + list(medium_top10)

    # Dedup por canonical_id
    seen = set()
    top_unique = []
    for it in top:
        if it.canonical_id in seen:
            continue
        seen.add(it.canonical_id)
        top_unique.append(it)
    top = top_unique

    lines.append("## Top priorizadas (acción recomendada)")
    if not top:
        lines.append("- No se identificaron ítems priorizados en el período.")
        lines.append("")
    else:
        for it in top:
            cvss = it.cvss if it.cvss is not None else "N/D"
            # tags/tech (si tenés un campo; si no, dejar vacío)
            tags = ", ".join(it.tech_tags.values_list("name", flat=True))


            lines.append(f"- **{it.canonical_id}** | {it.severity.upper()} | CVSS: {cvss}" + (f" | Tech: {tags}" if tags else ""))
            if it.primary_url:
                lines.append(f"  - Evidencia: {it.primary_url}")

            analysis = AIAnalysis.objects.filter(run=run, item=it).first()
            if analysis:
                if analysis.summary_es:
                    lines.append(f"  - Resumen: {analysis.summary_es}")
                if analysis.impact_previ:
                    lines.append(f"  - Impacto (Previ): {analysis.impact_previ}")
                if analysis.recommended_action:
                    lines.append(f"  - Acción recomendada: {analysis.recommended_action}")
                if analysis.recommended_deadline:
                    lines.append(f"  - Plazo sugerido: {analysis.recommended_deadline}")
                if analysis.requires_management:
                    lines.append("  - Requiere decisión de Dirección: **SI**")
                if analysis.notes:
                    lines.append(f"  - Notas: {analysis.notes}")
            else:
                lines.append("  - Análisis IA: No disponible (pendiente o deshabilitado)")

            lines.append("")

    # 4) Listado compacto del resto (opcional)
    lines.append("## Listado de relevantes (referencia)")
    rest = items_qs.exclude(canonical_id__in=[x.canonical_id for x in top]).order_by("-cvss")[:50]
    if rest:
        lines.append("Se listan los primeros 50 (ordenados por CVSS) para referencia:")
        for it in rest:
            cvss = it.cvss if it.cvss is not None else "N/D"
            url = it.primary_url or ""
            lines.append(f"- {it.canonical_id} | {it.severity} | CVSS: {cvss} | {url}")
    else:
        lines.append("- Sin ítems adicionales.")
    lines.append("")

    body_md = "\n".join(lines)

    # Si ya tenés conversión md->html, úsala. Si no, html básico:
    body_html = body_md.replace("\n", "<br>")

    return subject, body_md, body_html