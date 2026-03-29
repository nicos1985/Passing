"""Tareas asincrónicas para sincronización y alertas de documentos controlados."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import DocumentoControlado, IntegrationCredential
from .services import DriveFileNotFound, GoogleDriveService, GoogleDriveServiceError

logger = logging.getLogger(__name__)


def _get_active_credential() -> IntegrationCredential | None:
    return (
        IntegrationCredential.objects.filter(service=IntegrationCredential.Service.GOOGLE_DRIVE, status=IntegrationCredential.Status.ACTIVE)
        .order_by("-updated_at")
        .first()
    )


@shared_task
def process_drive_change(resource_id: str, channel_id: str | None = None, state: str | None = None) -> str:
    """Procesa la notificación de Drive para un archivo concreto."""
    try:
        doc = DocumentoControlado.objects.get(drive_file_id=resource_id)
    except DocumentoControlado.DoesNotExist:
        logger.info("Drive webhook: recurso %s no registrado", resource_id)
        return "documento_no_registrado"

    credential = doc.credencial or _get_active_credential()
    if not credential:
        logger.warning("Drive webhook sin credencial activa para doc %s", doc.id)
        return "sin_credencial"

    service = GoogleDriveService(credential)
    try:
        service.sync_documento(doc)
        return "ok"
    except DriveFileNotFound:
        doc.no_encontrado = True
        doc.ultima_sincronizacion = timezone.now()
        doc.save(update_fields=["no_encontrado", "ultima_sincronizacion"])
        return "no_encontrado"
    except GoogleDriveServiceError as exc:
        logger.exception("Error sincronizando cambio de Drive: %s", exc)
        return "error"


@shared_task
def check_vencimientos() -> dict:
    """Revisa documentos vencidos o próximos y deja huella para alertas.

    Aquí solo calculamos y registramos; el envío de notificaciones puede integrarse
    con el módulo existente de notifications.
    """
    resumen = {"vencido": 0, "proximo": 0, "al_dia": 0, "sin_datos": 0, "no_encontrado": 0}
    afectados: list[DocumentoControlado] = []

    for doc in DocumentoControlado.objects.all():
        estado = doc.estado_cumplimiento
        if estado in resumen:
            resumen[estado] += 1
        if estado in ("vencido", "proximo"):
            afectados.append(doc)

    if afectados:
        logger.info("Documentos con revisión pendiente: %s", [d.drive_file_id for d in afectados])
        # TODO: Integrar con notifications para avisar a responsables.

    return resumen
