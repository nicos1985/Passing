"""Small, redacted JSON snapshots stored only on incidents."""

import base64
import hashlib
import json
import math
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


MAX_EVIDENCE_CHARS = 4000
SENSITIVE_KEY = re.compile(r"pass(word)?|secret|token|auth|api.?key|cookie|session|credential|email|phone|address", re.I)


def _safe_value(value, depth=0):
    if depth >= 5:
        return "[más niveles omitidos]"
    if isinstance(value, dict):
        result = {}
        for key, child in list(value.items())[:20]:
            result[str(key)[:80]] = "[oculto]" if SENSITIVE_KEY.search(str(key)) else _safe_value(child, depth + 1)
        if len(value) > 20:
            result["_más_campos"] = len(value) - 20
        return result
    if isinstance(value, list):
        result = [_safe_value(child, depth + 1) for child in value[:5]]
        if len(value) > 5:
            result.append(f"[{len(value) - 5} elementos más]")
        return result
    if isinstance(value, str):
        return value[:200] + ("…" if len(value) > 200 else "")
    if isinstance(value, float) and not math.isfinite(value):
        return "[valor no estándar]"
    return value


def json_evidence(document):
    rendered = json.dumps(_safe_value(document), ensure_ascii=False, indent=2, allow_nan=False)
    return rendered[:MAX_EVIDENCE_CHARS], len(rendered) > MAX_EVIDENCE_CHARS


def _cipher():
    digest = hashlib.sha256(("passing-monitoring-evidence:" + settings.SECRET_KEY).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_evidence(text):
    return _cipher().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_evidence(token):
    if not token:
        return None
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None
