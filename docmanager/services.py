"""Servicios de integración con Google Drive usando Service Account.

Las credenciales se leen desde IntegrationCredential y se descifran con Fernet.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import DocumentoControlado, IntegrationCredential

logger = logging.getLogger(__name__)


class GoogleDriveServiceError(Exception):
    """Error genérico de la integración con Google Drive."""


class InvalidCredential(GoogleDriveServiceError):
    """La credencial no existe, está inactiva o no tiene secreto."""


class DriveFileNotFound(GoogleDriveServiceError):
    """Archivo no encontrado o eliminado en Drive."""


class GoogleDriveService:
    """Wrapper simple sobre Google Drive API v3 para usos del proyecto."""

    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self, credential: IntegrationCredential):
        if not credential:
            raise InvalidCredential("Se requiere una credencial activa para usar Drive.")
        if not credential.is_active:
            raise InvalidCredential("La credencial indicada no está activa.")
        self.credential = credential
        self._service = None

    # -------------------------
    # Inicialización del cliente
    # -------------------------
    def _client(self):
        if self._service:
            return self._service

        secret = self.credential.get_secret()
        if not secret:
            raise InvalidCredential("La credencial no tiene secreto configurado.")

        try:
            info = json.loads(secret)
            creds = Credentials.from_service_account_info(info, scopes=self.SCOPES)
        except Exception as exc:  # noqa: BLE001
            logger.exception("No se pudo construir las credenciales de servicio: %s", exc)
            raise InvalidCredential("No se pudo construir las credenciales de servicio.") from exc

        try:
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("No se pudo inicializar el cliente de Drive: %s", exc)
            raise GoogleDriveServiceError("Fallo al inicializar el cliente de Drive") from exc
        return self._service

    def list_revisions(self, file_id: str) -> list[dict]:
        """Devuelve revisiones de un archivo en Drive."""
        try:
            resp = (
                self._client()
                .revisions()
                .list(
                    fileId=file_id,
                    fields="revisions(id, modifiedTime, keepForever, lastModifyingUser(displayName,emailAddress), size, originalFilename, mimeType)",
                )
                .execute()
            )
            return resp.get("revisions", [])
        except HttpError as exc:  # type: ignore[attr-defined]
            if exc.resp.status == 404:
                raise DriveFileNotFound(f"Archivo {file_id} no encontrado") from exc
            raise GoogleDriveServiceError("Error obteniendo revisiones de Drive") from exc

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _parse_datetime(value: Optional[str]):
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    # -------------------------
    # Operaciones
    # -------------------------
    def fetch_metadata(self, file_id: str) -> dict:
        try:
            return (
                self._client()
                .files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, modifiedTime, webViewLink, lastModifyingUser(displayName,emailAddress)",
                )
                .execute()
            )
        except HttpError as exc:  # type: ignore[attr-defined]
            if exc.resp.status == 404:
                raise DriveFileNotFound(f"Archivo {file_id} no encontrado") from exc
            raise GoogleDriveServiceError("Error consultando metadata de Drive") from exc

    def listar_carpeta(self, carpeta_id: str) -> list[dict]:
        q = f"'{carpeta_id}' in parents and trashed = false"
        try:
            resp = (
                self._client()
                .files()
                .list(
                    q=q,
                    fields=(
                        "files(id, name, mimeType, parents, createdTime, modifiedTime, webViewLink, "
                        "lastModifyingUser(displayName,emailAddress))"
                    ),
                )
                .execute()
            )
        except HttpError as exc:  # type: ignore[attr-defined]
            if exc.resp.status == 404:
                raise DriveFileNotFound(f"Carpeta {carpeta_id} no encontrada") from exc
            raise GoogleDriveServiceError("Error listando carpeta en Drive") from exc

        archivos = resp.get("files", [])
        if not archivos:
            return []

        # Sincronizamos/creamos registros locales
        for item in archivos:
            self._apply_drive_item(item, carpeta_id)
        return archivos

    def _apply_drive_item(self, item: dict, carpeta_id: str | None = None) -> DocumentoControlado:
        drive_id = item.get("id")
        if not drive_id:
            raise GoogleDriveServiceError("Respuesta de Drive sin id de archivo")

        defaults = {
            "nombre_archivo": item.get("name", ""),
            "carpeta_drive_id": carpeta_id or "",
            "link_edicion": item.get("webViewLink") or "",
            "frecuencia_revision_dias": 90,
            "credencial": self.credential,
        }

        modified = self._parse_datetime(item.get("modifiedTime"))
        if modified:
            defaults["fecha_modificacion_drive"] = modified
        editor = item.get("lastModifyingUser")
        if editor:
            defaults["ultimo_editor_drive"] = editor.get("displayName") or editor.get("emailAddress") or ""

        with transaction.atomic():
            doc, _created = DocumentoControlado.objects.update_or_create(
                drive_file_id=drive_id,
                defaults=defaults,
            )
            doc.ultima_sincronizacion = timezone.now()
            doc.no_encontrado = False
            doc.save(update_fields=[
                "nombre_archivo",
                "carpeta_drive_id",
                "link_edicion",
                "frecuencia_revision_dias",
                "credencial",
                "fecha_modificacion_drive",
                "ultimo_editor_drive",
                "ultima_sincronizacion",
                "no_encontrado",
            ])
        return doc

    def sync_file(self, file_id: str) -> DocumentoControlado:
        metadata = self.fetch_metadata(file_id)
        doc = self._apply_drive_item(metadata)
        return doc

    def sync_documento(self, doc: DocumentoControlado) -> DocumentoControlado:
        doc.no_encontrado = False
        doc.save(update_fields=["no_encontrado"])
        return self.sync_file(doc.drive_file_id)

    def watch_file(self, file_id: str, webhook_url: str, channel_id: str | None = None, ttl_seconds: int = 86400) -> dict:
        """Registra un canal de notificación (push) hacia nuestro webhook.

        ttl_seconds: tiempo de vida del canal (Google limita a ~7 días).
        """
        channel_id = channel_id or str(uuid.uuid4())
        expiration_ms = int((timezone.now() + timedelta(seconds=ttl_seconds)).timestamp() * 1000)
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "token": str(self.credential.id),
            "expiration": expiration_ms,
        }
        try:
            return self._client().files().watch(fileId=file_id, body=body).execute()
        except HttpError as exc:  # type: ignore[attr-defined]
            if exc.resp.status == 404:
                raise DriveFileNotFound(f"Archivo {file_id} no encontrado para watch") from exc
            raise GoogleDriveServiceError("Error registrando webhook en Drive") from exc

    def about(self) -> dict:
        """Devuelve datos básicos de la cuenta de servicio en Drive."""
        try:
            return (
                self._client()
                    .about()
                    .get(fields="user(displayName,emailAddress),storageQuota(limit,usage),kind")
                    .execute()
            )
        except HttpError as exc:  # type: ignore[attr-defined]
            raise GoogleDriveServiceError("Error consultando información de la cuenta") from exc


def sync_file(file_id: str, credential: IntegrationCredential) -> DocumentoControlado:
    """Helper para sincronizar un archivo concreto con una credencial dada."""
    service = GoogleDriveService(credential)
    return service.sync_file(file_id)


def sync_folder(carpeta_id: str, credential: IntegrationCredential) -> list[dict]:
    service = GoogleDriveService(credential)
    return service.listar_carpeta(carpeta_id)
