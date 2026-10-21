"""Metadatos mínimos de soporte; nunca persistimos el cuerpo de los mensajes."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from passbase.crypto import decrypt_data, encrypt_data
from .links import group_url


class BitrixPortal(models.Model):
    name = models.CharField(max_length=100)
    base_url = models.URLField(max_length=255, unique=True)
    webhook_encrypted = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(null=True, blank=True)
    next_offset = models.BigIntegerField(null=True, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        permissions = [('view_support_inbox', 'Puede ver la bandeja de soporte')]

    def __str__(self):
        return self.name

    def set_webhook(self, value):
        self.webhook_encrypted = encrypt_data(value.rstrip('/') + '/')
        self.subscribed_at = None
        self.next_offset = None

    def webhook_url(self):
        if not self.webhook_encrypted:
            raise ValueError('El portal no tiene webhook configurado.')
        value = decrypt_data(self.webhook_encrypted)
        if not value:
            raise ValueError('No se pudo descifrar el webhook del portal.')
        return value

    @property
    def poll_is_stale(self):
        return self.enabled and self.last_polled_at is not None and (
            timezone.now() - self.last_polled_at > timedelta(minutes=5)
        )


class SupportChat(models.Model):
    portal = models.ForeignKey(BitrixPortal, on_delete=models.CASCADE, related_name='chats')
    label = models.CharField(max_length=100)
    dialog_id = models.CharField(max_length=50)
    link_url = models.URLField(max_length=500, blank=True)
    ignored_sender_ids = models.CharField(max_length=500, blank=True, help_text='IDs de usuarios de soporte separados por comas')
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ['portal__name', 'label']
        constraints = [models.UniqueConstraint(fields=['portal', 'dialog_id'], name='support_chat_per_portal')]

    def __str__(self):
        return f'{self.portal.name} · {self.label}'

    @property
    def open_url(self):
        return self.link_url or group_url(self.portal.base_url, self.dialog_id) or self.portal.base_url

    @property
    def ignored_ids(self):
        return {int(value) for value in self.ignored_sender_ids.split(',') if value.strip().isdigit()}


class TelegramRecipient(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_telegram')
    chat_id = models.BigIntegerField(unique=True)
    active = models.BooleanField(default=True)
    fallback = models.BooleanField(default=False, help_text='Recibe avisos si no hay turno activo')
    notify_support = models.BooleanField(default=True)
    notify_monitoring = models.BooleanField(default=False)
    notify_password_requests = models.BooleanField(default=False)
    notify_risks = models.BooleanField(default=False)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class TelegramPairing(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pending_chat_id = models.BigIntegerField()
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)


class TelegramBotConfig(models.Model):
    """Un bot por tenant; el token nunca se expone en formularios o plantillas."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    token_encrypted = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_token(self, value):
        self.token_encrypted = encrypt_data(value.strip())

    def token(self):
        if not self.token_encrypted:
            raise ValueError('El bot no tiene token configurado.')
        value = decrypt_data(self.token_encrypted)
        if not value:
            raise ValueError('No se pudo descifrar el token del bot.')
        return value


class DutyShift(models.Model):
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    primary = models.ForeignKey(TelegramRecipient, on_delete=models.PROTECT, related_name='primary_shifts')
    backup = models.ForeignKey(TelegramRecipient, on_delete=models.PROTECT, related_name='backup_shifts', null=True, blank=True)
    note = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-starts_at']

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError('El fin debe ser posterior al inicio.')
        if self.backup_id and self.backup_id == self.primary_id:
            raise ValidationError('El suplente debe ser otra persona.')


class SupportNotice(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Falló'

    chat = models.ForeignKey(SupportChat, on_delete=models.CASCADE, related_name='notices')
    first_at = models.DateTimeField()
    last_at = models.DateTimeField()
    notify_after = models.DateTimeField(db_index=True)
    message_count = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-last_at']


class SupportMessage(models.Model):
    portal = models.ForeignKey(BitrixPortal, on_delete=models.CASCADE)
    chat = models.ForeignKey(SupportChat, on_delete=models.CASCADE)
    notice = models.ForeignKey(SupportNotice, on_delete=models.CASCADE, related_name='messages')
    message_id = models.BigIntegerField()
    author_id = models.BigIntegerField()
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['portal', 'message_id'], name='support_message_per_portal')]


class TelegramDelivery(models.Model):
    notice = models.ForeignKey(SupportNotice, on_delete=models.CASCADE, related_name='deliveries')
    recipient = models.ForeignKey(TelegramRecipient, on_delete=models.PROTECT)
    status = models.CharField(max_length=8, choices=SupportNotice.Status.choices, default=SupportNotice.Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['notice', 'recipient'], name='support_delivery_once')]


class TelegramEventDelivery(models.Model):
    class Category(models.TextChoices):
        MONITORING = 'monitoring', 'Monitorización'
        PASSWORD_REQUEST = 'password_request', 'Solicitud de acceso'
        RISK_ASSISTANT = 'risk_assistant', 'Asistente de riesgos'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Falló'
        CANCELLED = 'cancelled', 'Cancelado'

    recipient = models.ForeignKey(TelegramRecipient, on_delete=models.CASCADE)
    category = models.CharField(max_length=24, choices=Category.choices)
    source_id = models.BigIntegerField()
    event = models.CharField(max_length=12, default='opened')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['recipient', 'category', 'source_id', 'event'], name='telegram_event_delivery_once',
        )]
