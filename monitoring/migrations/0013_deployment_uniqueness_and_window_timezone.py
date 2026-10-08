from django.db import migrations, models
from django.db.models import Count


def collapse_identical_deployments(apps, schema_editor):
    Marker = apps.get_model("monitoring", "DeploymentMarker")
    duplicates = (Marker.objects.using(schema_editor.connection.alias)
                  .values("monitor_id", "deployed_at", "version", "note")
                  .annotate(total=Count("id")).filter(total__gt=1))
    for group in duplicates:
        filters = {key: group[key] for key in ("monitor_id", "deployed_at", "version", "note")}
        ids = list(Marker.objects.using(schema_editor.connection.alias).filter(**filters).order_by("created_at", "id").values_list("id", flat=True))
        Marker.objects.using(schema_editor.connection.alias).filter(id__in=ids[1:]).delete()


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0012_schedules_heartbeats_deployments")]

    operations = [
        migrations.AddField(model_name="maintenancewindow", name="time_zone", field=models.CharField(default="UTC", max_length=64)),
        migrations.RunPython(collapse_identical_deployments, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="deploymentmarker", constraint=models.UniqueConstraint(fields=("monitor", "deployed_at", "version", "note"), name="monitoring_unique_deployment")),
    ]
