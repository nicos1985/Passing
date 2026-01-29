from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _first_str(*vals: Any) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def extract_description(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""

    # genérico
    desc = _first_str(
        payload.get("description"),
        payload.get("summary"),
        payload.get("detail"),
        payload.get("details"),
        payload.get("content"),
    )
    if desc:
        return desc

    # NVD v2 style: descriptions: [{lang, value}]
    descs = payload.get("descriptions")
    if isinstance(descs, list):
        for d in descs:
            if isinstance(d, dict) and d.get("lang") == "en" and d.get("value"):
                return str(d["value"]).strip()
        for d in descs:
            if isinstance(d, dict) and d.get("value"):
                return str(d["value"]).strip()

    return ""


def extract_references(payload: Dict[str, Any]) -> List[str]:
    if not payload:
        return []

    refs: List[str] = []

    # genérico
    for k in ("references", "refs", "urls", "links"):
        v = payload.get(k)
        if isinstance(v, list):
            for x in v:
                if isinstance(x, str) and x.strip():
                    refs.append(x.strip())
                elif isinstance(x, dict) and x.get("url"):
                    refs.append(str(x["url"]).strip())
        elif isinstance(v, str) and v.strip():
            refs.append(v.strip())

    # NVD v2: references: [{url:...}]
    v = payload.get("references")
    if isinstance(v, list):
        for r in v:
            if isinstance(r, dict) and r.get("url"):
                refs.append(str(r["url"]).strip())

    # dedup preservando orden
    seen = set()
    out = []
    for r in refs:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out
