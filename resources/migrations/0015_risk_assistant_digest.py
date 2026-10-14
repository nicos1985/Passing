from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('resources', '0014_risk_assistant')]

    operations = [
        migrations.AddField(
            model_name='riskassistantrun', name='digest_text',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='riskassistantrun', name='digest_ai_used',
            field=models.BooleanField(default=False),
        ),
    ]
