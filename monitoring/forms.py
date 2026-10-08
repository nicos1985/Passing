import ipaddress
import json
import re
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import DeploymentMarker, MaintenanceWindow, Monitor


HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
JSON_PATH = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+)(?:\.(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+))*$")


def validate_host(value):
    value = value.strip().rstrip(".")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if len(value) > 253 or not all(HOST_LABEL.fullmatch(label) for label in value.split(".")):
            raise ValidationError("Ingresá una IP o un nombre de host válido.")
    return value


def normalize_ping_target(value):
    value = value.strip()
    if value.lower().startswith(("http://", "https://")):
        try:
            parsed = urlsplit(value)
            if parsed.username or parsed.password or parsed.port or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValidationError("Para ping ingresá solo el dominio o una URL sin ruta, puerto ni parámetros.")
            value = parsed.hostname or ""
        except ValueError:
            raise ValidationError("Ingresá una URL válida.")
    return validate_host(value)


def normalize_http_target(value):
    value = value.strip()
    if len(value) > 500 or any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        raise ValidationError("Ingresá una URL HTTP/HTTPS válida de hasta 500 caracteres.")
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
            raise ValueError
        if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError
        port = parsed.port
        validate_host(parsed.hostname)
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
    except (ValueError, ValidationError):
        raise ValidationError("Ingresá una URL HTTP/HTTPS sin usuario, contraseña, parámetros ni fragmento.")
    return value


def parse_socket_target(value, default_port=None):
    value = value.strip()
    if value.startswith("["):
        match = re.fullmatch(r"\[([^\]]+)\](?::([0-9]{1,5}))?", value)
        if not match:
            raise ValidationError("Ingresá un host y puerto válidos; para IPv6 usá [dirección]:puerto.")
        host, port_text = match.groups()
        try:
            if ipaddress.ip_address(host).version != 6:
                raise ValueError
        except ValueError as exc:
            raise ValidationError("La dirección entre corchetes debe ser IPv6.") from exc
    else:
        if value.count(":") > 1:
            raise ValidationError("Para IPv6 usá [dirección]:puerto.")
        host, separator, port_text = value.partition(":")
        if not separator:
            port_text = None
        host = validate_host(host)
    if port_text is None and default_port is None:
        raise ValidationError("Indicá el puerto, por ejemplo example.com:5432.")
    try:
        port = int(port_text) if port_text is not None else default_port
    except ValueError as exc:
        raise ValidationError("El puerto debe estar entre 1 y 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValidationError("El puerto debe estar entre 1 y 65535.")
    return host, port


def normalize_socket_target(value, default_port=None):
    host, port = parse_socket_target(value, default_port)
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def parse_http_codes(value):
    """Accept a small list of exact codes and inclusive ranges."""
    codes = set()
    parts = [part.strip() for part in value.split(",")]
    if not parts or len(parts) > 20 or any(not part for part in parts):
        raise ValidationError("Indicá códigos HTTP separados por comas, por ejemplo 200-299,301.")
    for part in parts:
        if not re.fullmatch(r"[1-5][0-9]{2}(?:-[1-5][0-9]{2})?", part):
            raise ValidationError("Usá códigos de 100 a 599 y rangos como 200-299.")
        bounds = [int(item) for item in part.split("-")]
        start, end = (bounds[0], bounds[-1])
        if start > end or len(codes) + end - start + 1 > 300:
            raise ValidationError("El rango de códigos HTTP es inválido o demasiado amplio.")
        codes.update(range(start, end + 1))
    return codes


class MonitorForm(forms.ModelForm):
    class Meta:
        model = Monitor
        fields = ["name", "description", "kind", "host", "interval_seconds", "timeout_seconds", "expected_http_codes", "max_latency_ms", "json_path", "json_expected_value", "tls_min_days", "heartbeat_interval_minutes", "heartbeat_grace_minutes", "failure_threshold", "recovery_threshold", "recipients"]
        labels = {"host": "Destino", "expected_http_codes": "Códigos HTTP aceptados", "max_latency_ms": "Latencia máxima (ms)", "json_path": "Ruta del valor JSON", "json_expected_value": "Valor JSON esperado", "tls_min_days": "Avisar si vence en menos de (días)"}
        help_texts = {
            "name": "Nombre visible en el dashboard, incidentes y avisos.",
            "description": "Contexto opcional para el equipo. Evitá incluir contraseñas o datos sensibles.",
            "kind": "Elegí cómo comprobar el servicio: ping, HTTP, puerto TCP, certificado TLS o señal de una tarea.",
            "host": "Ping: dominio o IP. HTTP: URL completa. TCP: host:puerto. TLS: host o host:puerto (443 por defecto).",
            "interval_seconds": "Tiempo entre comprobaciones automáticas del destino. No se usa en tareas con señal.",
            "timeout_seconds": "Tiempo máximo de espera de cada comprobación antes de contarla como falla.",
            "expected_http_codes": "Ejemplo: 200-299,301. Se usa 200-299 si no se cambia.",
            "max_latency_ms": "Opcional. Una respuesta más lenta cuenta como falla.",
            "json_path": "Opcional. Claves e índices separados por puntos: health.status, items.0.status o 0.status si el JSON empieza con una lista.",
            "json_expected_value": 'Escribí un literal JSON: "ok", true, 1 o null. Se compara el tipo y el valor.',
            "tls_min_days": "Se comprueba la cadena y el nombre del certificado, además de su vencimiento.",
            "heartbeat_interval_minutes": "Cada cuántos minutos debe llegar una señal de éxito.",
            "heartbeat_grace_minutes": "Margen adicional antes de declarar una falla.",
            "failure_threshold": "Cantidad de fallas consecutivas necesarias para abrir un incidente.",
            "recovery_threshold": "Cantidad de checks correctos consecutivos para recuperar el servicio.",
            "recipients": "Direcciones de correo separadas por comas. Se avisa al abrir y recuperar incidentes.",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 2}), "recipients": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_http_codes"].required = False
        self.fields["tls_min_days"].required = False
        self.fields["host"].required = False
        self.fields["heartbeat_interval_minutes"].required = False
        self.fields["heartbeat_grace_minutes"].required = False
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{name}_help"

    def clean_host(self):
        kind = self.data.get("kind") or (self.instance.kind if self.instance.pk else Monitor.Kind.PING)
        if kind == Monitor.Kind.HEARTBEAT:
            return "Señal entrante"
        if kind == Monitor.Kind.HTTP:
            return normalize_http_target(self.cleaned_data["host"])
        if kind == Monitor.Kind.TCP:
            return normalize_socket_target(self.cleaned_data["host"])
        if kind == Monitor.Kind.TLS:
            return normalize_socket_target(self.cleaned_data["host"], default_port=443)
        return normalize_ping_target(self.cleaned_data["host"])

    def clean_recipients(self):
        raw = self.cleaned_data["recipients"]
        addresses = [item.strip() for item in raw.split(",") if item.strip()]
        if len(addresses) > 30:
            raise ValidationError("Se admiten hasta 30 destinatarios.")
        for address in addresses:
            validate_email(address)
        return ", ".join(dict.fromkeys(addresses))

    def clean_expected_http_codes(self):
        value = (self.cleaned_data["expected_http_codes"] or "200-299").strip()
        parse_http_codes(value)
        return value

    def clean_tls_min_days(self):
        return self.cleaned_data["tls_min_days"] or 30

    def clean_heartbeat_interval_minutes(self):
        return self.cleaned_data["heartbeat_interval_minutes"] or 1440

    def clean_heartbeat_grace_minutes(self):
        value = self.cleaned_data["heartbeat_grace_minutes"]
        return 15 if value is None else value

    def clean(self):
        cleaned = super().clean()
        path = (cleaned.get("json_path") or "").strip()
        expected = (cleaned.get("json_expected_value") or "").strip()
        if cleaned.get("kind") != Monitor.Kind.HTTP:
            cleaned.update(expected_http_codes="200-299", max_latency_ms=None, json_path="", json_expected_value="")
        if cleaned.get("kind") != Monitor.Kind.TLS:
            cleaned["tls_min_days"] = 30
        if cleaned.get("kind") == Monitor.Kind.HEARTBEAT:
            cleaned["failure_threshold"] = 1
            cleaned["recovery_threshold"] = 1
        if cleaned.get("kind") != Monitor.Kind.HTTP:
            return cleaned
        if bool(path) != bool(expected):
            self.add_error("json_path" if not path else "json_expected_value", "Completá ambos campos para comprobar el valor JSON.")
        if path and not JSON_PATH.fullmatch(path):
            self.add_error("json_path", "Usá claves separadas por puntos; se admiten índices numéricos para listas.")
        if expected:
            try:
                parsed = json.loads(expected)
            except (ValueError, TypeError):
                self.add_error("json_expected_value", "Ingresá un literal JSON válido, por ejemplo \"ok\" o true.")
            else:
                if isinstance(parsed, (dict, list)):
                    self.add_error("json_expected_value", "El valor esperado debe ser texto, número, booleano o null.")
        cleaned["json_path"] = path
        cleaned["json_expected_value"] = expected
        return cleaned


class MaintenanceWindowForm(forms.ModelForm):
    class Meta:
        model = MaintenanceWindow
        fields = ["monitor", "starts_at", "ends_at", "recurrence", "note", "enabled"]
        labels = {"starts_at": "Inicio", "ends_at": "Fin", "recurrence": "Repetición", "note": "Motivo"}
        help_texts = {
            "monitor": "Servicio al que se aplica esta ventana. Los checks continúan, pero se silencian sus notificaciones.",
            "starts_at": "Fecha y hora de inicio; en una recurrencia fija el primer día y la hora habitual.",
            "ends_at": "Fecha y hora de fin. En una recurrencia, la diferencia con el inicio define la duración.",
            "recurrence": "Una vez, todos los días o el mismo día de cada semana.",
            "note": "Motivo opcional, por ejemplo despliegue o mantenimiento del servidor.",
            "enabled": "Desmarcá para conservar la ventana sin aplicarla.",
        }
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{name}_help"

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("starts_at"), cleaned.get("ends_at")
        if start and end:
            duration = end - start
            if duration.total_seconds() <= 0:
                self.add_error("ends_at", "El fin debe ser posterior al inicio.")
            if cleaned.get("recurrence") != MaintenanceWindow.Recurrence.ONCE and duration.total_seconds() > 86400:
                self.add_error("ends_at", "Una ventana recurrente puede durar hasta 24 horas.")
        return cleaned


class DeploymentMarkerForm(forms.ModelForm):
    class Meta:
        model = DeploymentMarker
        fields = ["deployed_at", "version", "note"]
        labels = {"deployed_at": "Fecha y hora", "version": "Versión o despliegue", "note": "Nota"}
        help_texts = {
            "deployed_at": "Momento en que se hizo el cambio, en la zona horaria elegida arriba.",
            "version": "Identificador breve que aparecerá al pasar el cursor sobre la marca del gráfico.",
            "note": "Detalle opcional para relacionar el cambio con la latencia o los incidentes.",
        }
        widgets = {"deployed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{name}_help"
