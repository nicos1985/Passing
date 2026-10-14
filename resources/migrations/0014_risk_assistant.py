import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0013_risk_history_and_followup_review'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RiskAssistantRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(unique=True)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(default='running', max_length=16)),
                ('created_count', models.PositiveIntegerField(default=0)),
                ('ai_used', models.BooleanField(default=False)),
                ('error_code', models.CharField(blank=True, max_length=40)),
            ],
            options={'verbose_name': 'Ejecución del asistente de riesgos', 'ordering': ['-day']},
        ),
        migrations.CreateModel(
            name='RiskInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('review_draft', 'Reevaluación pendiente'), ('overdue_treatment', 'Tratamiento vencido'), ('stale_high_risk', 'Riesgo alto sin revisión reciente'), ('missing_treatment', 'Riesgo alto sin tratamiento')], max_length=32)),
                ('fingerprint', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('open', 'Abierta'), ('snoozed', 'Pospuesta'), ('reviewed', 'Revisada'), ('dismissed', 'Descartada'), ('superseded', 'Reemplazada')], default='open', max_length=16)),
                ('priority', models.CharField(choices=[('normal', 'Normal'), ('high', 'Alta')], default='normal', max_length=8)),
                ('reason_code', models.CharField(max_length=40)),
                ('summary', models.CharField(max_length=240)),
                ('suggested_action', models.CharField(max_length=32)),
                ('ai_used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('snoozed_until', models.DateField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assistant_insights', to='resources.riskevaluation')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='insights', to='resources.riskassistantrun')),
            ],
            options={'verbose_name': 'Sugerencia del asistente de riesgos', 'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='riskinsight',
            constraint=models.UniqueConstraint(fields=('evaluation', 'kind', 'fingerprint'), name='risk_insight_once_per_facts'),
        ),
    ]
