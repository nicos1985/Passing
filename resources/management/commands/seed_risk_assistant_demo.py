"""Carga casos sintéticos para probar el asistente sin tocar riesgos existentes."""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, tenant_context

from accounts.models import CustomUser
from resources.models import (
    AssetType, InformationAssets, RiskEvaluation, Threat, Vulnerability,
)


class Command(BaseCommand):
    help = 'Crea cinco evaluaciones sintéticas para probar el asistente de riesgos en un tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Schema del tenant de prueba, por ejemplo empresa1.')

    def handle(self, *args, **options):
        schema = options['tenant'].strip()
        tenant = get_tenant_model().objects.filter(schema_name=schema).exclude(schema_name='public').first()
        if tenant is None:
            raise CommandError('No existe ese tenant.')
        with tenant_context(tenant), transaction.atomic():
            owner = CustomUser.for_client(tenant).filter(is_active=True).order_by('-is_superuser', '-is_staff', 'pk').first()
            if owner is None:
                raise CommandError('El tenant necesita un usuario activo para asignar los activos de prueba.')
            threat, _ = Threat.objects.get_or_create(name='[RA-DEMO] Amenaza sintética')
            vulnerability, _ = Vulnerability.objects.get_or_create(name='[RA-DEMO] Vulnerabilidad sintética')
            content_type = ContentType.objects.get_for_model(InformationAssets)
            created = 0
            cases = (
                ('Borrador pendiente', 'draft', 2, 2),
                ('Tratamiento vencido', 'overdue', 5, 5),
                ('Riesgo alto antiguo', 'stale', 5, 5),
                ('Riesgo alto sin tratamiento', 'missing', 5, 5),
                ('Riesgo bajo al día', 'healthy', 1, 1),
            )
            for label, scenario, impact, probability in cases:
                asset, _ = InformationAssets.objects.get_or_create(
                    name=f'[RA-DEMO] {label}',
                    defaults={'owner': owner, 'asset_type': AssetType.SERVICE,
                              'description': 'Dato sintético para probar el asistente de riesgos.'},
                )
                evaluation, new = RiskEvaluation.objects.get_or_create(
                    evaluated_type=content_type, evaluated_id=asset.pk,
                    threat=threat, vulnerability=vulnerability,
                    defaults={
                        'description': f'[RA-DEMO] Caso {scenario}.',
                        'confidenciality_impact': impact,
                        'integrity_impact': impact,
                        'availability_impact': impact,
                        'probability': probability,
                        'is_draft': scenario in {'draft', 'missing'},
                    },
                )
                if not new:
                    continue
                created += 1
                if scenario == 'overdue':
                    evaluation.treatment.deadline = timezone.localdate() - timedelta(days=7)
                    evaluation.treatment.save(update_fields=['deadline', 'updated'])
                elif scenario == 'stale':
                    RiskEvaluation.objects.filter(pk=evaluation.pk).update(
                        updated=timezone.now() - timedelta(days=200),
                    )
                elif scenario == 'missing':
                    # Representa un registro histórico importado sin tratamiento.
                    RiskEvaluation.objects.filter(pk=evaluation.pk).update(is_draft=False)
        self.stdout.write(self.style.SUCCESS(
            f'{schema}: {created} evaluaciones demo nuevas; 4 deberían generar sugerencias.'
        ))
