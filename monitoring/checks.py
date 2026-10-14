import json
import platform
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone

import requests

from .forms import normalize_http_target, parse_http_codes, parse_socket_target, validate_host
from .models import CheckResult, Monitor
from .evidence import json_evidence


def ping(host, timeout_seconds):
    """One ICMP probe. Never passes an editable destination to a shell."""
    host = validate_host(host)
    system = platform.system()
    if system == "Linux":
        command = ["ping", "-n", "-c", "1", "-W", str(int(timeout_seconds)), "--", host]
    elif system == "Windows":
        command = ["ping", "-n", "1", "-w", str(int(timeout_seconds * 1000)), host]
    else:
        return CheckResult.Status.ERROR, None, "Sistema operativo no soportado para ping"
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout_seconds + 2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return CheckResult.Status.ERROR, None, "No se pudo ejecutar ping"
    latency = round((time.monotonic() - started) * 1000)
    if result.returncode == 0:
        return CheckResult.Status.OK, latency, ""
    if result.returncode == 1:
        return CheckResult.Status.FAILURE, None, "Sin respuesta ICMP"
    return CheckResult.Status.ERROR, None, "Error al ejecutar ping"


MAX_JSON_BYTES = 16 * 1024
NO_DOCUMENT = object()


def _json_value(document, path):
    value = document
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


def _with_evidence(result, document, capture_json):
    return (*result, json_evidence(document)) if capture_json and document is not NO_DOCUMENT else result


def http_check(url, timeout_seconds, expected_codes="200-299", max_latency_ms=None, json_path="", json_expected_value="", capture_json=False):
    """Read headers, and at most 16 KiB for an optional JSON assertion."""
    url = normalize_http_target(url)
    accepted = parse_http_codes(expected_codes)
    session = requests.Session()
    session.trust_env = False
    document = NO_DOCUMENT
    try:
        started = time.monotonic()
        response = session.get(url, timeout=timeout_seconds, allow_redirects=False, stream=True)
        try:
            latency = round((time.monotonic() - started) * 1000)
            code = response.status_code
            assert_json = bool(code in accepted and json_path)
            content_type = response.headers.get("Content-Type", "").lower()
            capture_failure_json = bool(capture_json and (json_path or "json" in content_type) and (
                code not in accepted or (max_latency_ms is not None and latency > max_latency_ms)
            ))
            if assert_json or capture_failure_json:
                body = bytearray()
                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdecimal() and int(content_length) > MAX_JSON_BYTES:
                    if assert_json:
                        return CheckResult.Status.FAILURE, latency, "Respuesta JSON demasiado grande", code
                else:
                    for chunk in response.iter_content(chunk_size=4096):
                        body.extend(chunk)
                        if len(body) > MAX_JSON_BYTES:
                            if assert_json:
                                return CheckResult.Status.FAILURE, round((time.monotonic() - started) * 1000), "Respuesta JSON demasiado grande", code
                            break
                    if len(body) <= MAX_JSON_BYTES:
                        latency = round((time.monotonic() - started) * 1000)
                        try:
                            document = json.loads(body.decode("utf-8"))
                        except (UnicodeError, ValueError):
                            if assert_json:
                                return CheckResult.Status.FAILURE, latency, "La respuesta no es JSON válido", code
                        else:
                            if assert_json:
                                try:
                                    actual = _json_value(document, json_path)
                                except (KeyError, TypeError, ValueError):
                                    return _with_evidence((CheckResult.Status.FAILURE, latency, f"Ruta JSON no encontrada: {json_path}", code), document, capture_json)
                                expected = json.loads(json_expected_value)
                                if type(actual) is not type(expected) or actual != expected:
                                    return _with_evidence((CheckResult.Status.FAILURE, latency, f"Valor JSON inesperado en {json_path}", code), document, capture_json)
        finally:
            response.close()
    except requests.exceptions.Timeout:
        return CheckResult.Status.FAILURE, None, "Tiempo de espera agotado", None
    except requests.exceptions.SSLError:
        return CheckResult.Status.FAILURE, None, "Error TLS o certificado", None
    except requests.exceptions.ConnectionError:
        return CheckResult.Status.FAILURE, None, "Error de conexión o DNS", None
    except requests.exceptions.ChunkedEncodingError:
        return CheckResult.Status.FAILURE, None, "Respuesta HTTP incompleta", None
    except requests.exceptions.RequestException:
        return CheckResult.Status.ERROR, None, "No se pudo ejecutar el check HTTP", None
    finally:
        session.close()
    if code in accepted and max_latency_ms is not None and latency > max_latency_ms:
        return _with_evidence((CheckResult.Status.SLOW, latency, f"Latencia {latency} ms supera {max_latency_ms} ms (HTTP {code})", code), document, capture_json)
    if code in accepted:
        return CheckResult.Status.OK, latency, f"HTTP {code}", code
    if 200 <= code < 300:
        reason = f"HTTP {code} no esperado"
    elif 300 <= code < 400:
        reason = f"Redirección HTTP {code}"
    elif code == 401:
        reason = "Autenticación requerida (HTTP 401)"
    elif code == 403:
        reason = "Acceso prohibido (HTTP 403)"
    elif code == 404:
        reason = "No encontrado (HTTP 404)"
    elif code == 429:
        reason = "Límite de solicitudes (HTTP 429)"
    elif 500 <= code < 600:
        reason = f"Error del servidor (HTTP {code})"
    else:
        reason = f"Respuesta HTTP {code}"
    return _with_evidence((CheckResult.Status.FAILURE, latency, reason, code), document, capture_json)


def tcp_check(target, timeout_seconds):
    host, port = parse_socket_target(target)
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            latency = round((time.monotonic() - started) * 1000)
    except (TimeoutError, socket.timeout):
        return CheckResult.Status.FAILURE, None, "Tiempo de espera agotado en puerto TCP", None
    except OSError:
        return CheckResult.Status.FAILURE, None, "Puerto TCP inaccesible o conexión rechazada", None
    return CheckResult.Status.OK, latency, f"TCP {port} abierto", None


def tls_check(target, timeout_seconds, min_days):
    host, port = parse_socket_target(target, default_port=443)
    context = ssl.create_default_context()
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as connection:
            connection.settimeout(timeout_seconds)
            with context.wrap_socket(connection, server_hostname=host) as secure:
                certificate = secure.getpeercert()
                latency = round((time.monotonic() - started) * 1000)
    except ssl.SSLCertVerificationError:
        return CheckResult.Status.FAILURE, None, "Certificado TLS inválido, vencido o no confiable", None
    except ssl.SSLError:
        return CheckResult.Status.FAILURE, None, "No se pudo completar TLS", None
    except (TimeoutError, socket.timeout):
        return CheckResult.Status.FAILURE, None, "Tiempo de espera agotado en TLS", None
    except OSError:
        return CheckResult.Status.FAILURE, None, "No se pudo conectar al puerto TLS", None
    if not certificate.get("notAfter"):
        return CheckResult.Status.FAILURE, latency, "Certificado TLS sin vencimiento verificable", None
    try:
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate["notAfter"]), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return CheckResult.Status.FAILURE, latency, "Vencimiento TLS inválido", None
    remaining = expires - datetime.now(timezone.utc)
    days = max(0, remaining.days)
    if remaining.total_seconds() < min_days * 86400:
        return CheckResult.Status.FAILURE, latency, f"Certificado TLS vence en {days} días", None
    return CheckResult.Status.OK, latency, f"Certificado TLS válido; vence en {days} días", None


def run_check(monitor):
    if monitor.kind == Monitor.Kind.PING:
        return (*ping(monitor.host, monitor.timeout_seconds), None)
    if monitor.kind == Monitor.Kind.HTTP:
        return http_check(monitor.host, monitor.timeout_seconds, monitor.expected_http_codes, monitor.max_latency_ms, monitor.json_path, monitor.json_expected_value, capture_json=True)
    if monitor.kind == Monitor.Kind.TCP:
        return tcp_check(monitor.host, monitor.timeout_seconds)
    if monitor.kind == Monitor.Kind.TLS:
        return tls_check(monitor.host, monitor.timeout_seconds, monitor.tls_min_days)
    return CheckResult.Status.ERROR, None, "Tipo de check no soportado", None
