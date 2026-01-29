# threat_intel/services/normalize.py
from __future__ import annotations

import hashlib
from typing import Optional

from django.utils import timezone

from threat_intel.models import IntelItem, RawItem
from threat_intel.services.normalize_text import extract_description, extract_references


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _severity_from_cvss(cvss):
    if cvss is None:
        return "unknown"
    try:
        cvss_f = float(cvss)
    except Exception:
        return "unknown"
    if cvss_f >= 9.0:
        return "critical"
    if cvss_f >= 7.0:
        return "high"
    if cvss_f >= 4.0:
        return "medium"
    return "low"


def upsert_intel_item_from_raw(raw: RawItem) -> IntelItem:
    source_code = raw.source.code
    payload = raw.raw_payload or {}

    # Texto/referencias: usar extractor SIEMPRE (cubrir NVD/CISA/RSS/vendors)
    desc = extract_description(payload)
    refs = extract_references(payload)

    # published_at: preferir el publicado del raw; fallback a fetched_at; si no existe, now()
    published_at = getattr(raw, "published_at", None) or getattr(raw, "fetched_at", None) or timezone.now()

    # 1) canonical_id + kind + title + url + cvss
    if source_code == "NVD":
        # raw.external_id debería ser CVE-XXXX-YYYY
        canonical_id = raw.external_id or (raw.url and f"NVD:{_hash(raw.url)}") or f"NVD:{_hash(raw.title or '')}"
        kind = "cve"
        title = raw.title or payload.get("title") or canonical_id
        primary_url = raw.url or (refs[0] if refs else "")
        cvss = payload.get("cvss")  # ajusta si tu normalizador NVD guarda otro key
    else:
        base = raw.url or raw.external_id or raw.title or ""
        canonical_id = f"{source_code}:{_hash(base)}"
        kind = "bulletin"
        title = raw.title or payload.get("title") or "Advisory"
        primary_url = raw.url or (refs[0] if refs else "")
        cvss = payload.get("cvss")  # la mayoría no trae; quedará None

    severity = _severity_from_cvss(cvss)

    # 2) Consolidación de refs: incluir url primaria + refs extraídas
    refs_set = []
    seen = set()
    for u in [primary_url] + (refs or []) + ([raw.url] if raw.url else []):
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        refs_set.append(u)

    # 3) Upsert
    intel_item, created = IntelItem.objects.update_or_create(
        canonical_id=canonical_id,
        defaults={
            "kind": kind,
            "title": title,
            "description": desc or "",          # <- clave
            "cvss": cvss,
            "severity": severity,
            "published_at": published_at,
            "primary_url": primary_url or "",   # tu modelo no tiene blank=True, así que evitar None
            "references": refs_set,
        },
    )

    # 4) Evidencia de fuente
    # raw.source es FK -> Source, y IntelItem.sources es M2M
    if raw.source_id:
        intel_item.sources.add(raw.source)

    return intel_item
