from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0010_incident_json_evidence_encrypted_and_more")]

    operations = [
        migrations.AddField(model_name="incident", name="bitrix_resolved_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="incident", name="bitrix_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="incident", name="bitrix_sync_error", field=models.CharField(blank=True, max_length=240)),
    ]
