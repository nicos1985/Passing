# threat_intel/sources/nvd.py
from __future__ import annotations
import requests
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .base import BaseConnector

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def _requests_session_with_retry() -> requests.Session:
    s = requests.Session()

    retry = Retry(
        total=6,
        connect=3,
        read=3,
        backoff_factor=1.2,  # 0s, 1.2s, 2.4s, 4.8s...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class NvdConnector(BaseConnector):
    code = "NVD"

    def fetch(self, start_dt, end_dt, cursor=None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Trae CVEs PUBLICADOS en el rango [start_dt, end_dt].
        Paginación por startIndex.
        """
        session = _requests_session_with_retry()

        # IMPORTANTE: params se define siempre acá, antes del loop
        params = {
            "pubStartDate": start_dt.isoformat(),
            "pubEndDate": end_dt.isoformat(),
            "resultsPerPage": 2000,
            "startIndex": 0,
            "noRejected": "",
        }

        items: List[Dict[str, Any]] = []

        while True:
            r = session.get(
                NVD_BASE,
                params=params,
                timeout=(10, 60),
                headers={"User-Agent": "Passing-ThreatIntel/1.0"},
            )

            if r.status_code >= 400:
                raise RuntimeError(f"NVD error {r.status_code}: {r.text[:200]}")

            data = r.json()
            vulns = data.get("vulnerabilities", []) or []

            for v in vulns:
                cve = (v.get("cve") or {})
                cve_id = cve.get("id")
                if not cve_id:
                    continue

                # Title/description (NVD v2: descriptions[] con lang)
                desc = ""
                for d in (cve.get("descriptions") or []):
                    if d.get("lang") == "en":
                        desc = d.get("value") or ""
                        break
                if not desc and (cve.get("descriptions") or []):
                    desc = (cve["descriptions"][0].get("value") or "")

                # Fechas (published/lastModified)
                published_at = _parse_iso_datetime(cve.get("published"))
                last_modified = _parse_iso_datetime(cve.get("lastModified"))

                # Referencias
                refs = []
                for ref in (cve.get("references") or []):
                    url = ref.get("url")
                    if url:
                        refs.append(url)

                # CVSS (si está)
                cvss = None
                metrics = cve.get("metrics") or {}
                # priorizar v3.1, luego v3.0, luego v2
                for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                    arr = metrics.get(key) or []
                    if arr:
                        cvss_data = (arr[0].get("cvssData") or {})
                        score = cvss_data.get("baseScore")
                        try:
                            cvss = float(score) if score is not None else None
                        except (TypeError, ValueError):
                            cvss = None
                        break

                primary_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

                items.append({
                    "external_id": cve_id,
                    "published_at": published_at or last_modified,  # fallback
                    "url": primary_url,
                    "title": cve_id,
                    "payload": {
                        "description": desc,
                        "references": refs[:50],
                        "cvss": cvss,
                        "published": cve.get("published"),
                        "lastModified": cve.get("lastModified"),
                    },
                })

            total = int(data.get("totalResults") or 0)
            start_index = int(params["startIndex"])
            per_page = int(params["resultsPerPage"])

            # ¿Hay más páginas?
            if start_index + per_page >= total:
                break

            params["startIndex"] = start_index + per_page

            # Pausa suave para reducir 503/rate issues
            time.sleep(0.7)

        new_cursor = {"last_run_end": end_dt.isoformat(), "mode": "published"}
        return items, new_cursor


def _parse_iso_datetime(dt_str: str | None):
    if not dt_str:
        return None

    s = dt_str.strip()
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)

    return dt
