from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.conf import settings
from .models import CustomUser, TwoFAChange
from django_tenants.utils import schema_context
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=CustomUser)
def capture_old_2fa(sender, instance, **kwargs):
    """Store old is_2fa_enabled value on the instance prior to save.

    Always read the value from the `public` schema where `CustomUser` is stored
    to avoid inconsistencies when the current connection schema is a tenant.
    """
    if not instance.pk:
        instance._old_is_2fa_enabled = None
        return
    try:
        with schema_context('public'):
            old = sender.objects.filter(pk=instance.pk).values_list('is_2fa_enabled', flat=True).first()
        instance._old_is_2fa_enabled = bool(old) if old is not None else None
    except Exception as e:
        logger.exception('Could not capture old is_2fa_enabled for user %s: %s', getattr(instance, 'pk', None), e)
        instance._old_is_2fa_enabled = None


@receiver(post_save, sender=CustomUser)
def record_2fa_change(sender, instance, created, **kwargs):
    """If is_2fa_enabled changed, create a TwoFAChange record in `public`.

    Uses `schema_context('public')` to ensure the audit model (shared app)
    always writes to the public schema even if the request is serving a tenant.
    """
    old = getattr(instance, '_old_is_2fa_enabled', None)
    new = bool(instance.is_2fa_enabled)
    try:
        if old is None and created:
            if new:
                with schema_context('public'):
                    TwoFAChange.objects.create(user=instance, old_value=None, new_value=new, source='create')
                logger.info('TwoFAChange: created for new user %s -> %s', instance.pk, new)
            return

        if old != new:
            try:
                with schema_context('public'):
                    TwoFAChange.objects.create(user=instance, old_value=old, new_value=new, source='post_save')
                logger.info('TwoFAChange recorded for user %s: %s -> %s', instance.pk, old, new)
            except Exception:
                logger.exception('Failed to create TwoFAChange for user %s', instance.pk)
    except Exception:
        logger.exception('Unhandled error in record_2fa_change for user %s', getattr(instance, 'pk', None))
*** End Patch