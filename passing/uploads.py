from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


def validate_attachment(upload):
    if isinstance(upload, UploadedFile):
        if upload.size > getattr(settings, 'MAX_ATTACHMENT_BYTES', 10 * 1024 * 1024):
            raise ValidationError('El archivo supera el máximo de 10 MB.')
        if Path(upload.name).suffix.lower() not in {'.pdf', '.txt', '.csv', '.png', '.jpg', '.jpeg', '.xlsx', '.docx', '.zip'}:
            raise ValidationError('Tipo de archivo no permitido.')
    return upload
