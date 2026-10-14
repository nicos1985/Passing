from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0013_deployment_uniqueness_and_window_timezone")]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="kind",
            field=models.CharField(choices=[("failure", "Falla"), ("slow", "Respuesta lenta")], default="failure", max_length=12),
        ),
        migrations.AddField(
            model_name="incident",
            name="end_reason",
            field=models.CharField(choices=[("recovered", "Recuperado"), ("escalated", "Escaló a caída"), ("slowed", "Pasó a respuesta lenta")], default="recovered", max_length=12),
        ),
        migrations.AlterField(
            model_name="monitor",
            name="state",
            field=models.CharField(choices=[("unknown", "Sin datos"), ("up", "Saludable"), ("slow", "Respuesta lenta"), ("down", "Caído")], default="unknown", max_length=12),
        ),
        migrations.AlterField(
            model_name="checkresult",
            name="status",
            field=models.CharField(choices=[("ok", "Correcto"), ("slow", "Respuesta lenta"), ("failure", "Falla"), ("error", "Error del monitor")], max_length=8),
        ),
    ]
