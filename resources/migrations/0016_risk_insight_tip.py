from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('resources', '0015_risk_assistant_digest')]

    operations = [
        migrations.AddField(
            model_name='riskinsight', name='tip',
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name='riskinsight', name='tip_ai_used',
            field=models.BooleanField(default=False),
        ),
    ]
