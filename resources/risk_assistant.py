"""Sugerencias de riesgos por reglas, con priorización externa de datos abstractos."""

import hashlib
import json
import re
import os
import unicodedata
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .models import LevelOfRisk, RiskAssistantRun, RiskEvaluation, RiskInsight, TreatmentStage


ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')
STALE_DAYS = 180

LABELS = {
    RiskInsight.Kind.REVIEW_DRAFT: ('Hay una reevaluación pendiente de confirmar.', 'review'),
    RiskInsight.Kind.OVERDUE_TREATMENT: ('El tratamiento asociado está vencido.', 'inspect'),
    RiskInsight.Kind.STALE_HIGH_RISK: ('El riesgo alto requiere una revisión periódica.', 'review'),
    RiskInsight.Kind.MISSING_TREATMENT: ('El riesgo alto no tiene tratamiento asociado.', 'create_treatment'),
}

VULNERABILITY_FAMILIES = {
    0: 'hardware', 1: 'software', 2: 'network', 3: 'people',
    4: 'physical', 5: 'organization', 6: 'process', 7: 'commercial', 8: 'other',
}

# Solo se envían estas etiquetas fijas; nunca fragmentos de texto libre.
THEME_PATTERNS = {
    'access_control': r'\b(acceso|accesos|permiso|permisos|privilegio|privilegios|cuenta|cuentas|credencial|credenciales)\b',
    'authentication': r'\b(mfa|2fa|autenticacion|contrasena|contrasenas|password|passwords)\b',
    'patching': r'\b(parche|parches|actualizacion|actualizaciones|obsoleto|obsoleta)\b',
    'backups': r'\b(backup|backups|respaldo|respaldos|copia de seguridad|copias de seguridad)\b',
    'encryption': r'\b(cifrado|cifrada|cifrar|encriptacion|encriptado)\b',
    'availability': r'\b(disponibilidad|caida|caidas|interrupcion|interrupciones)\b',
    'logging': r'\b(log|logs|auditoria|trazabilidad|registro de eventos)\b',
    'network_security': r'\b(firewall|segmentacion|puerto|puertos|redes|red)\b',
    'supplier': r'\b(proveedor|proveedores|tercero|terceros)\b',
    'training': r'\b(capacitacion|concientizacion|formacion)\b',
}

LOCAL_TIPS = {
    RiskInsight.Kind.REVIEW_DRAFT: 'Abrí la evaluación, confirmá impacto y probabilidad y dejá registrada la revisión.',
    RiskInsight.Kind.OVERDUE_TREATMENT: 'Abrí el tratamiento, actualizá etapa y plazo, y registrá la próxima acción con su responsable.',
    RiskInsight.Kind.STALE_HIGH_RISK: 'Revisá si el riesgo sigue vigente y registrá una nueva evaluación con evidencia.',
    RiskInsight.Kind.MISSING_TREATMENT: 'Definí un tratamiento con responsable, próximo paso y fecha de seguimiento.',
}


def _theme_tags(evaluation):
    source = ' '.join((evaluation.description or '', evaluation.vulnerability.description or ''))[:10000]
    normalized = ''.join(char for char in unicodedata.normalize('NFKD', source.lower()) if not unicodedata.combining(char))
    return [tag for tag, pattern in THEME_PATTERNS.items() if re.search(pattern, normalized)][:4]


def _safe_tip(value):
    if not isinstance(value, str):
        return None
    tip = ' '.join(value.split())
    if not 25 <= len(tip) <= 260:
        return None
    if re.search(r'https?://|www\.|@|\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[a-z0-9-]+\.(?:com|net|org|ar|io|local)\b|\b\+?\d[\d .()-]{7,}\d\b', tip, re.I):
        return None
    if not re.search(r'revis|defin|actualiz|confirm|registr|planific|verific|coordina|prioriz|document|comprob', tip, re.I):
        return None
    return tip

DIGEST_LABELS = {
    RiskInsight.Kind.REVIEW_DRAFT: ('evaluación pendiente', 'evaluaciones pendientes'),
    RiskInsight.Kind.OVERDUE_TREATMENT: ('tratamiento vencido', 'tratamientos vencidos'),
    RiskInsight.Kind.STALE_HIGH_RISK: ('riesgo alto sin revisión reciente', 'riesgos altos sin revisión reciente'),
    RiskInsight.Kind.MISSING_TREATMENT: ('riesgo alto sin tratamiento', 'riesgos altos sin tratamiento'),
}


def _digest_stats(run):
    """Solo cantidades y categorías de la lista cerrada; no consulta texto libre."""
    open_insights = RiskInsight.objects.filter(status=RiskInsight.Status.OPEN)
    by_kind = {kind: 0 for kind in DIGEST_LABELS}
    for row in open_insights.values('kind').annotate(total=Count('pk')):
        if row['kind'] in by_kind:
            by_kind[row['kind']] = row['total']
    return {
        'open_count': sum(by_kind.values()),
        'new_today': run.insights.filter(status=RiskInsight.Status.OPEN).count(),
        'high_count': open_insights.filter(priority=RiskInsight.Priority.HIGH).count(),
        'by_kind': by_kind,
    }


def _top_open_tip():
    order = {
        RiskInsight.Kind.OVERDUE_TREATMENT: 0,
        RiskInsight.Kind.MISSING_TREATMENT: 1,
        RiskInsight.Kind.REVIEW_DRAFT: 2,
        RiskInsight.Kind.STALE_HIGH_RISK: 3,
    }
    insights = RiskInsight.objects.filter(status=RiskInsight.Status.OPEN).exclude(tip='').only(
        'priority', 'kind', 'tip',
    )
    top = min(insights, key=lambda item: (
        item.priority != RiskInsight.Priority.HIGH,
        order.get(item.kind, 9),
    ), default=None)
    return top.tip if top else ''


def _digest_facts(stats):
    if not stats['open_count']:
        return ''
    parts = [f'{count} {DIGEST_LABELS[kind][0 if count == 1 else 1]}'
             for kind, count in stats['by_kind'].items() if count]
    details = ', '.join(parts[:-1]) + (' y ' if len(parts) > 1 else '') + parts[-1]
    opening = (f'Buen día 👋 Revisé los riesgos y hay {stats["open_count"]} '
               f'{"tema" if stats["open_count"] == 1 else "temas"} para mirar: {details}.')
    priority = (f' {stats["high_count"]} de prioridad alta.' if stats['high_count'] else '')
    return opening + priority


def _local_digest(stats):
    if not stats['open_count']:
        return ''
    return _digest_facts(stats) + ' Podés revisarlos en Passing cuando tengas un momento.'


def _ai_digest(stats, client):
    if client is None or not stats['open_count']:
        return None
    system = (
        'Sos un asistente de gestión de riesgos. La aplicación ya escribió las cifras y los tipos. '
        'Redactá SOLO una frase adicional, cercana y útil, en español rioplatense, que sugiera '
        'por dónde empezar a revisar según las categorías presentes. No repitas cifras ni escribas '
        'números. Estos son riesgos para revisar, no incidentes. No inventes causas, sistemas, '
        'activos, nombres, organizaciones ni personas. No incluyas enlaces: la aplicación agrega '
        'el enlace verificado. Máximo 180 caracteres. Respondé JSON {"message":"..."}.'
    )
    try:
        result = json.loads(client.create_message(
            system, json.dumps(stats, separators=(',', ':'), sort_keys=True),
            temperature=0.3, max_tokens=220,
        ))
        message = result.get('message') if isinstance(result, dict) else None
        if not isinstance(message, str):
            return None
        message = message.strip()
        if not 20 <= len(message) <= 180 or re.search(r'\d|incident', message, re.I):
            return None
        # El texto del proveedor nunca puede introducir destinatarios o enlaces externos.
        if re.search(r'https?://|www\.|@|\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[a-z0-9-]+\.(?:com|net|org|ar|io|local)\b', message, re.I):
            return None
        return message
    except Exception:
        return None


def _candidates(day):
    """Convierte descripciones locales en etiquetas permitidas antes de salir del tenant."""
    for evaluation in RiskEvaluation.objects.select_related('treatment', 'vulnerability').all().iterator():
        age = max(0, (day - timezone.localtime(evaluation.updated, ARGENTINA).date()).days)
        level = evaluation.risk_level if evaluation.risk_level in range(5) else 0
        base = {
            'level': level,
            'age_days': min(age, 9999),
            'vulnerability_family': VULNERABILITY_FAMILIES.get(evaluation.vulnerability.type_vulnerability, 'other'),
            'themes': _theme_tags(evaluation),
        }
        if evaluation.is_draft:
            yield evaluation, RiskInsight.Kind.REVIEW_DRAFT, dict(base)
            continue
        treatment = evaluation.treatment
        if treatment and treatment.stage != TreatmentStage.IMPLEMENTED and treatment.deadline < day:
            yield evaluation, RiskInsight.Kind.OVERDUE_TREATMENT, {
                **base, 'overdue_days': min((day - treatment.deadline).days, 9999),
                'treatment_stage': int(treatment.stage),
            }
        if level >= LevelOfRisk.HIGH:
            if age >= STALE_DAYS:
                yield evaluation, RiskInsight.Kind.STALE_HIGH_RISK, dict(base)
            if treatment is None:
                yield evaluation, RiskInsight.Kind.MISSING_TREATMENT, dict(base)


def _ai_choices(candidates, client):
    """El único punto de salida a IA. Refs efímeras; sin IDs de base ni texto libre."""
    if not candidates or client is None:
        return {}
    results = {}
    system = (
        'Sos un asistente cercano de gestión de riesgos. Para cada caso, priorizá y proponé '
        'UN próximo paso concreto para ayudar a completar la tarea. Usá SOLO el tipo de caso, '
        'nivel, plazos, familia de vulnerabilidad y etiquetas temáticas dadas. Las etiquetas '
        'provienen de descripciones privadas que NO estás viendo. No inventes causas, sistemas, '
        'nombres, personas, fechas exactas ni controles ya implementados. No incluyas enlaces, '
        'IPs ni datos de contacto. La recomendación debe ser amable, en español rioplatense, '
        'de hasta 260 caracteres, y empezar con un verbo de acción. '
        'Respondé JSON: {"items":[{"ref":"R1","priority":"high|normal",'
        '"tip":"Revisá..."}]}.'
    )
    for start in range(0, len(candidates), 20):
        batch = candidates[start:start + 20]
        refs = {f'R{i + 1}': item for i, item in enumerate(batch)}
        payload = {'items': [
            {'ref': ref, 'kind': item[1], **item[2]} for ref, item in refs.items()
        ]}
        try:
            raw = client.create_message(system, json.dumps(payload, separators=(',', ':')), temperature=0.2, max_tokens=1600)
            answer = json.loads(raw)
            if not isinstance(answer, dict) or not isinstance(answer.get('items'), list):
                continue
            for choice in answer['items']:
                if not isinstance(choice, dict) or choice.get('ref') not in refs:
                    continue
                item = refs[choice['ref']]
                priority = choice.get('priority') if choice.get('priority') in RiskInsight.Priority.values else None
                tip = _safe_tip(choice.get('tip'))
                if priority or tip:
                    results[(item[0].pk, item[1])] = {'priority': priority, 'tip': tip}
        except Exception:
            # Una falla externa no impide generar sugerencias con reglas locales.
            continue
    return results


def run_daily(day=None, client=None, force=False, use_ai=True):
    day = day or timezone.now().astimezone(ARGENTINA).date()
    run, created = RiskAssistantRun.objects.get_or_create(day=day)
    if not created and run.status == 'complete' and not force:
        return run
    if not created and run.status == 'running' and not force and run.started_at > timezone.now() - timedelta(hours=1):
        return run
    if not created:
        run.status = 'running'
        run.error_code = ''
        run.started_at = timezone.now()
        run.save(update_fields=['status', 'error_code', 'started_at'])
    try:
        candidates = list(_candidates(day))
        items = []
        for evaluation, kind, facts in candidates:
            # La antigüedad y los días de vencimiento cambian solos; no definen un caso nuevo.
            treatment = evaluation.treatment
            fingerprint = hashlib.sha256(json.dumps([
                kind, evaluation.updated.isoformat(),
                treatment.updated.isoformat() if treatment else None,
                facts['vulnerability_family'], facts['themes'],
            ], separators=(',', ':')).encode()).hexdigest()
            items.append((evaluation, kind, facts, fingerprint))
        pending = []
        for item in items:
            previous = RiskInsight.objects.filter(
                evaluation=item[0], kind=item[1], fingerprint=item[3],
            ).only('status', 'tip_ai_used').first()
            if previous is None or (
                previous.status in {RiskInsight.Status.OPEN, RiskInsight.Status.SNOOZED}
                and not previous.tip_ai_used
            ):
                pending.append(item[:3])
        ai_enabled = use_ai and getattr(settings, 'RISK_ASSISTANT_AI_ENABLED', bool(getattr(settings, 'OPENAI_API_KEY', '')))
        if client is None and ai_enabled and getattr(settings, 'OPENAI_API_KEY', ''):
            try:
                if os.name == 'nt':
                    from .openai_windows import WindowsOpenAIClient
                    client = WindowsOpenAIClient()
                else:
                    from threat_intel.services.openai_api import get_openai_api_client
                    client = get_openai_api_client()
            except (ValueError, RuntimeError):
                client = None
        choices = _ai_choices(pending, client if ai_enabled else None)
        with transaction.atomic():
            current_keys = set()
            for evaluation, kind, facts, fingerprint in items:
                current_keys.add((evaluation.pk, kind, fingerprint))
                choice = choices.get((evaluation.pk, kind), {})
                priority = choice.get('priority') or (
                    RiskInsight.Priority.HIGH if facts['level'] >= LevelOfRisk.HIGH else RiskInsight.Priority.NORMAL
                )
                tip = choice.get('tip') or LOCAL_TIPS[kind]
                insight, was_created = RiskInsight.objects.get_or_create(
                    evaluation=evaluation, kind=kind, fingerprint=fingerprint,
                    defaults={'run': run, 'priority': priority, 'reason_code': kind,
                              'summary': LABELS[kind][0], 'tip': tip,
                              'tip_ai_used': bool(choice.get('tip')),
                              'suggested_action': LABELS[kind][1],
                              'ai_used': (evaluation.pk, kind) in choices},
                )
                if not was_created and not insight.tip_ai_used:
                    if choice.get('tip'):
                        insight.tip = choice['tip']
                        insight.tip_ai_used = True
                        insight.ai_used = True
                        insight.save(update_fields=['tip', 'tip_ai_used', 'ai_used', 'updated_at'])
                    elif not insight.tip:
                        insight.tip = LOCAL_TIPS[kind]
                        insight.save(update_fields=['tip', 'updated_at'])
            for insight in RiskInsight.objects.filter(status__in=[
                RiskInsight.Status.OPEN, RiskInsight.Status.SNOOZED,
            ]).only('pk', 'evaluation_id', 'kind', 'fingerprint'):
                if (insight.evaluation_id, insight.kind, insight.fingerprint) not in current_keys:
                    RiskInsight.objects.filter(pk=insight.pk).update(status=RiskInsight.Status.SUPERSEDED)
            RiskInsight.objects.filter(status=RiskInsight.Status.SNOOZED, snoozed_until__lt=day).update(
                status=RiskInsight.Status.OPEN, snoozed_until=None,
            )
        stats = _digest_stats(run)
        digest_ai = _ai_digest(stats, client) if ai_enabled else None
        top_tip = _top_open_tip()
        with transaction.atomic():
            run.status = 'complete'
            run.finished_at = timezone.now()
            run.created_count = sum(
                1 for key in run.insights.values_list('evaluation_id', 'kind', 'fingerprint')
                if key in current_keys
            )
            run.digest_text = (_digest_facts(stats) + ' ' + digest_ai) if digest_ai else _local_digest(stats)
            if top_tip:
                run.digest_text += f'\n\nPara avanzar hoy: {top_tip}'
            run.digest_ai_used = bool(digest_ai)
            run.ai_used = run.ai_used or bool(choices) or bool(digest_ai)
            run.save(update_fields=[
                'status', 'finished_at', 'created_count', 'digest_text', 'digest_ai_used', 'ai_used',
            ])
            if stats['open_count']:
                from supporthub.telegram_events import queue_risk_assistant_digest
                queue_risk_assistant_digest(run.pk)
    except Exception:
        run.status = 'failed'
        run.error_code = 'processing_error'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_code', 'finished_at'])
        raise
    return run


def run_due():
    now = timezone.now().astimezone(ARGENTINA)
    if now.hour >= 9:
        return run_daily(now.date())
    return None
