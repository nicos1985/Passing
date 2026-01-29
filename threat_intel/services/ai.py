
# threat_intel/services/ai.py
from __future__ import annotations

import json
from datetime import timezone as dt_timezone
from typing import Any

from django.utils import timezone
import traceback
from threat_intel.models import AIAnalysis, IntelItem, Run
from threat_intel.services.openai_api import get_openai_api_client


PROMPT_V1_SYSTEM = """Sos analista de ciberseguridad para una empresa de software pequeña.
Tu tarea es analizar vulnerabilidades/boletines SOLO con la información provista.
NO inventes CVSS, productos, versiones ni explotación si no está en el texto.
Si falta un dato, indicá "No especificado".

Respondé ÚNICAMENTE en JSON válido, sin texto adicional.

Stack de la organización (para evaluar aplicabilidad):
- Ubuntu
- MySQL
- Laravel (PHP + Composer)
- Frontend (Node/NPM supply chain)
- AWS (EC2, IAM, VPC, SSM, ALB, CloudWatch, RDS)
- Cloudflare WAF
- Fortinet (si aparece)

Clasificación por CVSS:
- critical >= 9.0
- high 7.0-8.9
- medium 4.0-6.9
- low < 4.0
Si no hay CVSS, priority="medium" y aclararlo.
 
 IMPORTANT: Return the JSON object using the exact ENGLISH key names below. Do not wrap the JSON in any markdown or explanatory text.
 Use these keys (example types shown):
 - `cve` (string)
 - `severity` (string)
 - `cvss` (number)
 - `description` (string)
 - `summary` (string)  # pequeño resumen en español
 - `impact` (string)   # analisis de impacto preliminar en español
 - `recommended_action` (array|string) # acciones recomendadas en español
 - `affected_tech` (array|string)
 - `notes` (string)
 - `recommended_deadline` (string)
 - `applies_to_stack` (boolean)
 - `priority` (string)
 - `requires_management` (boolean)
 - `evidence_url` (string)
 - `additional_references` (array)

If you cannot find a field in the provided text, set it to "No especificado" (for strings) or an empty list/false as appropriate.
"""

# Para recortar el texto y evitar costos / desbordes
MAX_TEXT_CHARS = 4500


def _build_item_text(item: IntelItem) -> str:
    """Construye el texto a enviar al modelo para análisis."""
    refs = item.references or []
    refs_txt = "\n".join(refs[:10])  # limitar
    cvss_txt = str(item.cvss) if item.cvss is not None else "null"

    blob = f"""ID: {item.canonical_id}
        Tipo: {item.kind}
        Título: {item.title}
        Descripción: {item.description or "No especificado"}
        CVSS: {cvss_txt}
        Severidad (normalizada): {item.severity}
        URL evidencia: {item.primary_url or "No especificado"}
        Otras referencias:
        {refs_txt}

        Objetivo: determinar aplicabilidad al stack y acciones recomendadas.
        """
    if len(blob) > MAX_TEXT_CHARS:
        blob = blob[:MAX_TEXT_CHARS] + "\n\n[TRUNCADO]"
    return blob


def _safe_json_loads(s: str) -> dict[str, Any]:
    """
    Parser defensivo: intenta extraer JSON aunque venga con espacios.
    (Idealmente el modelo devuelve JSON puro; igual conviene robustez)
    """
    s = s.strip()
    # Si viene envuelto en ```json ... ```
    if s.startswith("```"):
        s = s.strip("`")
        # remover posible 'json' inicial
        s = s.replace("json", "", 1).strip()
    return json.loads(s)


def _normalize_ai_response(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize keys coming from the model into the internal DB field names.

    The model is instructed to return English keys (preferred). However it may
    sometimes return Spanish or alternate key names. This function maps both
    English and common Spanish keys into the DB-facing keys used below.
    """
    mapping = {
        # preferred English -> DB field
        "summary": "summary_es",
        "impact": "impact_previ",
        "recommended_action": "recommended_action",
        "recommended_deadline": "recommended_deadline",
        "affected_tech": "affected_tech",
        "notes": "notes",
        "applies_to_stack": "applies_to_stack",
        "priority": "priority",
        "requires_management": "requires_management",

        # Spanish common variants -> DB field
        "descripcion": "summary_es",
        "resumen": "summary_es",
        "summary_es": "summary_es",
        "impacto": "impact_previ",
        "impact_previ": "impact_previ",
        "acciones_recomendadas": "recommended_action",
        "acciones": "recommended_action",
        "recommended_actions": "recommended_action",
        "productos_afectados": "affected_tech",
        "afecta_stack": "applies_to_stack",
        "aplicabilidad": "applies_to_stack",
        "url_evidencia": "evidence_url",
        "referencias_adicionales": "additional_references",
    }

    normalized: dict[str, Any] = {}

    # First, map any known keys
    for k, v in data.items():
        key = k.strip() if isinstance(k, str) else k
        dest = mapping.get(key)
        if dest:
            # prefer to keep the original type
            normalized[dest] = v
        else:
            # if the key is already a DB field name, keep it
            if key in mapping.values():
                normalized[key] = v
            else:
                # store unknown keys as-is to preserve data
                normalized[key] = v

    # Ensure types are consistent for some fields
    if "affected_tech" in normalized and isinstance(normalized["affected_tech"], str):
        normalized["affected_tech"] = [normalized["affected_tech"]]

    # Provide defaults for fields we expect later when creating AIAnalysis
    defaults = {
        "summary_es": "",
        "applies_to_stack": False,
        "affected_tech": [],
        "impact_previ": "",
        "recommended_action": "",
        "recommended_deadline": "",
        "priority": "medium",
        "requires_management": False,
        "notes": "",
    }
    for dk, dv in defaults.items():
        normalized.setdefault(dk, dv)

    return normalized


def analyze_item(client: Any, item: IntelItem, model_name: str, prompt_version: str) -> dict[str, Any]:
    """
    Analiza un ítem usando el cliente OpenAI API.
    
    Args:
        client: OpenAIAPIClient
        item: IntelItem a analizar
        model_name: Nombre del modelo
        prompt_version: Versión del prompt
        
    Returns:
        dict: Datos analizados
    """
    user_text = _build_item_text(item)

    try:
        out = client.create_message(
            system_prompt=PROMPT_V1_SYSTEM,
            user_message=user_text,
            temperature=0.7,
            max_tokens=2000,
        )
    except Exception as e:
        print(f"[AI] Error calling OpenAI: {e}", flush=True)
        raise
    
    #print("AI raw output:", out)
    data = _safe_json_loads(out)
    #print("AI parsed data:", data)
    
    # Normalize keys (handle English or Spanish keys returned by the model)
    normalized = _normalize_ai_response(data)
    return normalized


def analyze_relevant_items_for_run(run: Run) -> int:
    """
    Analiza:
    - todos los relevant critical/high
    - + top N medium relevantes por cvss
    Crea/actualiza AIAnalysis con unique(item, run)
    """
    # Obtener cliente OpenAI API (sin SDK problemático)
    #print("[AI] Inicializando OpenAI API client...", flush=True)
    try:
        client = get_openai_api_client()
    except Exception as e:
        print(f"[AI] ERROR creando cliente: {e}", flush=True)
        raise
    
    # Configuración
    model_name = client.model
    cfg = getattr(__import__('django.conf', fromlist=['settings']).settings, 'THREAT_INTEL', {})
    prompt_version = cfg.get("AI_PROMPT_VERSION", "v1")
    medium_top_n = int(cfg.get("AI_MEDIUM_TOP_N", 10))
    # global cap on number of items to analyze in a single run (useful for tests)
    max_items = cfg.get("AI_MAX_ITEMS")
    if max_items is not None:
        try:
            max_items = int(max_items)
        except Exception:
            max_items = None
    
    #print(f"[AI] Modelo: {model_name}, Prompt: {prompt_version}", flush=True)
    #print(f"[AI] Top N medium: {medium_top_n}", flush=True)

    #print("armando queryset base...", flush=True)
    qs = (IntelItem.objects
        .filter(runitem__run=run, is_relevant=True)
        .distinct())
    #print("queryset base OK (aún no evaluado)", flush=True)

    #print("evaluando critical/high...", flush=True)
    crit_high = list(qs.filter(severity__in=["critical", "high"]).order_by("-cvss")[:200])
    #print(f"critical/high list OK: {len(crit_high)}", flush=True)

    #print("evaluando medium...", flush=True)
    medium = list(qs.filter(severity="medium").order_by("-cvss")[:medium_top_n])
    #print(f"medium list OK: {len(medium)}", flush=True)

    to_analyze = crit_high + medium
    # apply optional global cap
    if max_items is not None and max_items >= 0:
        to_analyze = to_analyze[:max_items]
    #print(f"Items to analyze: {len(to_analyze)}", flush=True)

    processed = 0
    for item in to_analyze:
        if AIAnalysis.objects.filter(run=run, item=item).exists():
            continue

        try:
            data = analyze_item(client, item, model_name=model_name, prompt_version=prompt_version)
        except Exception as e:
            print(f"[AI] Failed for {item.canonical_id}: {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            continue
        #print(f"[AI] Analysis for {item.canonical_id}: {data}")
        # Sanitize/normalize values to avoid DB field length errors and
        # ensure consistent types (strings for TextField/CharField)
        def _as_text(v):
            if v is None:
                return ""
            if isinstance(v, (list, tuple)):
                return "\n".join(map(str, v))
            return str(v)

        summary_es = _as_text(data.get("summary_es", ""))
        impact_previ = _as_text(data.get("impact_previ", ""))
        recommended_action = _as_text(data.get("recommended_action", ""))
        recommended_deadline = _as_text(data.get("recommended_deadline", ""))[:60]
        notes = _as_text(data.get("notes", ""))
        affected_tech_val = data.get("affected_tech", []) or []
        if isinstance(affected_tech_val, str):
            affected_tech_val = [affected_tech_val]

        priority = (data.get("priority") or "medium").lower()[:20]
        model_name = str(model_name)[:80]
        prompt_version = str(prompt_version)[:40]

        AIAnalysis.objects.create(
            run=run,
            item=item,
            summary_es=summary_es,
            applies_to_stack=bool(data.get("applies_to_stack", False)),
            affected_tech=affected_tech_val,
            impact_previ=impact_previ,
            recommended_action=recommended_action,
            recommended_deadline=recommended_deadline,
            priority=priority,
            requires_management=bool(data.get("requires_management", False)),
            notes=notes,
            model_name=model_name,
            prompt_version=prompt_version,
        )
        processed += 1

    return processed
