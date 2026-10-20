"""Keep personal credentials out of sharing and role assignments."""

from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from permission.models import ContraPermission, PermissionRoles
from .models import Contrasena


@receiver(post_save, sender=Contrasena)
def remove_personal_sharing(sender, instance, raw=False, using=None, update_fields=None, **kwargs):
    if raw or (update_fields is not None and 'is_personal' not in update_fields and 'owner' not in update_fields and 'owner_id' not in update_fields):
        return
    if not instance.is_personal:
        return
    ContraPermission.objects.using(using).filter(contra_id=instance).exclude(user_id=instance.owner_id).delete()
    # Clear stale role links; this does not grant access to anyone else.
    instance.roles.clear()


@receiver(m2m_changed, sender=PermissionRoles.contrasenas.through)
def reject_personal_role_assignment(sender, instance, action, reverse, pk_set, using, **kwargs):
    if action != 'pre_add' or not pk_set:
        return
    personal = Contrasena.objects.using(using).filter(pk=instance.pk, is_personal=True).exists() if reverse else Contrasena.objects.using(using).filter(pk__in=pk_set, is_personal=True).exists()
    if personal:
        raise ValidationError('Las contraseñas personales no pueden pertenecer a un rol.')
