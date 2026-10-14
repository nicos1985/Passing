import django.db.models.deletion
from django.db import migrations, models


def repair_risk_defaults(apps, schema_editor):
    Vulnerability = apps.get_model('resources', 'Vulnerability')
    RiskEvaluation = apps.get_model('resources', 'RiskEvaluation')
    Vulnerability.objects.using(schema_editor.connection.alias).filter(type_vulnerability=16).update(type_vulnerability=8)
    RiskEvaluation.objects.using(schema_editor.connection.alias).filter(followup_for__isnull=False).update(is_draft=True)


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0012_riskevaluation_followup_for_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='riskevaluation', name='is_draft',
            field=models.BooleanField(default=False, verbose_name='Pendiente de reevaluación'),
        ),
        migrations.AddField(
            model_name='riskevaluation', name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, editable=False, verbose_name='Fecha de confirmación'),
        ),
        migrations.AddField(
            model_name='riskevaluation', name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, editable=False, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_risk_evaluations', to='accounts.customuser', verbose_name='Confirmada por'),
        ),
        migrations.AlterField(
            model_name='riskevaluation', name='threat',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='resources.threat', verbose_name='Amenaza'),
        ),
        migrations.AlterField(
            model_name='riskevaluation', name='vulnerability',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='resources.vulnerability', verbose_name='Vulnerabilidad'),
        ),
        migrations.AlterField(
            model_name='riskevaluation', name='treatment',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='risk_evaluation', to='resources.treatment', verbose_name='Tratamiento asociado'),
        ),
        migrations.AlterField(
            model_name='riskevaluation', name='followup_for',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='followup_evaluation', to='resources.treatment', verbose_name='Reevaluación posterior a tratamiento'),
        ),
        migrations.AlterField(
            model_name='treatment', name='treatment_responsible',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='accounts.customuser', verbose_name='Responsable de tratamiento'),
        ),
        migrations.AlterField(
            model_name='vulnerability', name='type_vulnerability',
            field=models.IntegerField(choices=[(0, 'Hardware'), (1, 'Software'), (2, 'Red'), (3, 'Personal'), (4, 'Lugar'), (5, 'Organizacion'), (6, 'Procesos'), (7, 'Comercial'), (8, 'Otros')], default=8, verbose_name='Tipo de vulnerabilidad'),
        ),
        migrations.RunPython(repair_risk_defaults, migrations.RunPython.noop),
    ]
