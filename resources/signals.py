from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Treatment, RiskEvaluation, TreatmentStage
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

@receiver(post_save, sender=Treatment)
def treatment_post_save(sender, instance: Treatment, created, **kwargs):
    """Cuando un tratamiento alcanza IMPLEMENTED, genera una re-evaluación del mismo objeto y evita crear otro tratamiento automáticamente."""
    try:
        if instance.stage == TreatmentStage.IMPLEMENTED:
            # find last evaluation for this object (excluding ones created at the same time)
            evaluations = RiskEvaluation.objects.filter(evaluated_type=instance.content_type, evaluated_id=instance.object_id).order_by('-created')
            base = evaluations.first()

            # prepare prefilled values
            if base:
                new_eval = RiskEvaluation(
                    evaluated_type=instance.content_type,
                    evaluated_id=instance.object_id,
                    threat=base.threat,
                    vulnerability=base.vulnerability,
                    description=(f"Re-evaluación posterior a implementación del tratamiento #{instance.pk}.\n" + (base.description or "")),
                    confidenciality_impact=base.confidenciality_impact,
                    integrity_impact=base.integrity_impact,
                    availability_impact=base.availability_impact,
                    probability=base.probability,
                )
            else:
                # minimal re-evaluation if no base exists
                new_eval = RiskEvaluation(
                    evaluated_type=instance.content_type,
                    evaluated_id=instance.object_id,
                    description=(f"Re-evaluación posterior a implementación del tratamiento #{instance.pk}.")
                )

            # mark to skip automatic treatment creation in save()
            setattr(new_eval, 'skip_treatment', True)
            # link the new re-evaluation to the treatment that triggered it
            try:
                new_eval.treatment = instance
            except Exception:
                pass
            new_eval.save()
    except Exception:
        # Avoid breaking main flow - logging could be added
        pass
