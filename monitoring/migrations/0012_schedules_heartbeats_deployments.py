import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0011_incident_bitrix_resolution"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(model_name="monitor", name="kind", field=models.CharField(choices=[("ping", "Ping (ICMP)"), ("http", "HTTP/HTTPS"), ("tcp", "Puerto TCP"), ("tls", "Certificado TLS"), ("heartbeat", "Tarea programada")], default="ping", max_length=16)),
        migrations.AddField(model_name="monitor", name="heartbeat_interval_minutes", field=models.PositiveIntegerField(default=1440, validators=[MinValueValidator(1), MaxValueValidator(10080)])),
        migrations.AddField(model_name="monitor", name="heartbeat_grace_minutes", field=models.PositiveIntegerField(default=15, validators=[MinValueValidator(0), MaxValueValidator(1440)])),
        migrations.AddField(model_name="monitor", name="heartbeat_token_hash", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="monitor", name="heartbeat_last_signal_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="MaintenanceWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("recurrence", models.CharField(choices=[("once", "Una vez"), ("daily", "Diariamente"), ("weekly", "Semanalmente")], default="once", max_length=8)),
                ("note", models.CharField(blank=True, max_length=160)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("monitor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_windows", to="monitoring.monitor")),
            ],
            options={"ordering": ["starts_at"]},
        ),
        migrations.CreateModel(
            name="DeploymentMarker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("deployed_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("version", models.CharField(max_length=80)),
                ("note", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("monitor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deployments", to="monitoring.monitor")),
            ],
            options={"ordering": ["-deployed_at"]},
        ),
    ]
