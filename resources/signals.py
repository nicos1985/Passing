import logging
from django.db.models.signals import post_save, pre_save, pre_delete
from django.db.models.deletion import ProtectedError
from django.dispatch import receiver
from .models import (
    Treatment, RiskEvaluation, TreatmentStage, InformationAssets,
    Vendor, Project, ClientCompany,
)
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Treatment)
def remember_treatment_stage(sender, instance, **kwargs):
    instance._previous_stage = (
        Treatment.objects.filter(pk=instance.pk).values_list('stage', flat=True).first()
        if instance.pk else None
    )

@receiver(post_save, sender=Treatment)
def treatment_post_save(sender, instance: Treatment, created, **kwargs):
    """Prepara una reevaluación para revisión humana al implementar un tratamiento."""
    try:
        if instance.stage == TreatmentStage.IMPLEMENTED and (
            created or getattr(instance, '_previous_stage', None) != TreatmentStage.IMPLEMENTED
        ) and not RiskEvaluation.objects.filter(followup_for=instance).exists():
            # Solo la evaluación que originó este tratamiento puede ser el punto de partida.
            base = RiskEvaluation.objects.filter(treatment=instance).first()

            # prepare prefilled values
            if base:
                new_eval = RiskEvaluation(
                    evaluated_type=instance.content_type,
                    evaluated_id=instance.object_id,
                    threat=base.threat,
                    vulnerability=base.vulnerability,
                    description=(f"Reevaluación pendiente del tratamiento #{instance.pk}. Revisar impacto y probabilidad antes de confirmar.\n" + (base.description or "")),
                    confidenciality_impact=base.confidenciality_impact,
                    integrity_impact=base.integrity_impact,
                    availability_impact=base.availability_impact,
                    probability=base.probability,
                    is_draft=True,
                )
            else:
                logger.warning('Treatment %s implemented without an existing risk evaluation', instance.pk)
                return

            # Preserve the original evaluation's one-to-one treatment link.
            new_eval.followup_for = instance
            new_eval.save()
    except Exception:
        logger.exception('Could not create follow-up evaluation for treatment %s', instance.pk)
        raise


def protect_evaluated_resource(sender, instance, using, **kwargs):
    """GenericForeignKey no aplica integridad referencial al borrar un recurso."""
    content_type = ContentType.objects.db_manager(using).get_for_model(sender)
    evaluations = RiskEvaluation.objects.using(using).filter(
        evaluated_type=content_type, evaluated_id=instance.pk,
    )
    treatments = Treatment.objects.using(using).filter(
        content_type=content_type, object_id=instance.pk,
    )
    if evaluations.exists() or treatments.exists():
        raise ProtectedError(
            'El recurso tiene evaluaciones o tratamientos de riesgo y no puede eliminarse.',
            list(evaluations) + list(treatments),
        )


for resource_model in (InformationAssets, Vendor, Project, ClientCompany):
    pre_delete.connect(
        protect_evaluated_resource, sender=resource_model,
        dispatch_uid=f'resources.protect_risk_history.{resource_model._meta.model_name}',
    )
