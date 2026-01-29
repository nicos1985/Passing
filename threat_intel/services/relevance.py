from __future__ import annotations

from typing import Dict, List, Tuple

from django.db import transaction

from threat_intel.models import IntelItem, Run, TechTag


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _build_haystack(item: IntelItem) -> str:
    # Con tu modelo, el texto útil está en title/description + urls
    parts = [
        item.canonical_id or "",
        item.title or "",
        item.description or "",
        " ".join(item.references or []),
        item.primary_url or "",
    ]
    return _norm(" ".join(parts))


def _compile_keywords() -> Dict[int, List[str]]:
    """
    Dict[tag_id] -> list[keywords_normalized]
    """
    out: Dict[int, List[str]] = {}
    for t in TechTag.objects.filter(is_active=True):
        kws = [_norm(k) for k in (t.keywords or []) if _norm(k)]
        if kws:
            out[t.id] = kws
    return out


def mark_relevance_for_run(run: Run) -> Tuple[int, int, int]:
    """
    Para items del run:
    - calcula relevancia por match de keywords
    - asigna M2M tech_tags para los relevantes
    - setea is_relevant True/False

    Returns: (total_items, relevant_items, updated_items)
    """
    kw_by_tag = _compile_keywords()
    if not kw_by_tag:
        total = IntelItem.objects.filter(runitem__run=run).distinct().count()
        return total, 0, 0

    tags_by_id = {t.id: t for t in TechTag.objects.filter(id__in=kw_by_tag.keys())}

    qs = IntelItem.objects.filter(runitem__run=run).distinct()

    total = 0
    relevant = 0
    updated = 0

    # Para bulk_update de boolean (rápido)
    to_update: List[IntelItem] = []
    # Para M2M: acumulamos asignaciones por item_id
    m2m_assign: Dict[int, List[int]] = {}

    for item in qs.iterator(chunk_size=500):
        total += 1
        hay = _build_haystack(item)

        matched_tag_ids: List[int] = []
        for tag_id, kws in kw_by_tag.items():
            for k in kws:
                if k and k in hay:
                    matched_tag_ids.append(tag_id)
                    break

        is_rel = len(matched_tag_ids) > 0
        if is_rel:
            relevant += 1

        # boolean
        if item.is_relevant != is_rel:
            item.is_relevant = is_rel
            to_update.append(item)

        # M2M: solo si relevante (si no, dejamos vacío)
        m2m_assign[item.id] = matched_tag_ids

    # Persistencia
    with transaction.atomic():
        if to_update:
            IntelItem.objects.bulk_update(to_update, ["is_relevant"], batch_size=1000)
            updated = len(to_update)

        # Set M2M:
        # - si relevante -> set matched tags
        # - si no relevante -> clear
        # Nota: .set() hace deletes/inserts; para 4k items es aceptable mensual.
        # Si querés optimizar luego, hacemos bulk sobre la tabla through.
        items_map = {it.id: it for it in IntelItem.objects.filter(id__in=m2m_assign.keys())}
        for item_id, tag_ids in m2m_assign.items():
            it = items_map.get(item_id)
            if not it:
                continue
            if tag_ids:
                it.tech_tags.set(tag_ids)
            else:
                it.tech_tags.clear()

    return total, relevant, updated
