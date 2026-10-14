import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Count, F


DATE_MODELS = (
    'ChecklistItem', 'ChecklistTemplate', 'ClientCompany', 'InformationAssets',
    'Project', 'RiskEvaluation', 'Threat', 'Treatment', 'Vendor',
    'VendorChecklist', 'VendorEvaluation', 'VendorEvaluationItem', 'Vulnerability',
)


def swap_legacy_dates(apps, schema_editor):
    """Existing 'updated' values hold creation dates; preserve them."""
    for model_name in DATE_MODELS:
        model = apps.get_model('resources', model_name)
        model.objects.using(schema_editor.connection.alias).update(
            created=F('updated'), updated=F('created'),
        )


def remove_identical_checklist_duplicates(apps, schema_editor):
    """Remove duplicate snapshots only when their answers are identical."""
    item_model = apps.get_model('resources', 'VendorEvaluationItem')
    fields = (
        'evaluation_id', 'checklist_item_id', 'question_text',
        'required', 'controls', 'result', 'observations',
    )
    groups = (
        item_model.objects.using(schema_editor.connection.alias)
        .values(*fields).annotate(total=Count('pk')).filter(total__gt=1)
    )
    for group in groups.iterator():
        filters = {field: group[field] for field in fields}
        ids = list(
            item_model.objects.using(schema_editor.connection.alias)
            .filter(**filters).order_by('pk').values_list('pk', flat=True)
        )
        item_model.objects.using(schema_editor.connection.alias).filter(pk__in=ids[1:]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0011_alter_vendorchecklist_template_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='informationassets', name='acquisition_date',
            field=models.DateField(default=django.utils.timezone.localdate, verbose_name='Fecha de adquisicion'),
        ),
        migrations.AddField(
            model_name='riskevaluation',
            name='followup_for',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='followup_evaluation', to='resources.treatment',
                verbose_name='Reevaluación posterior a tratamiento',
            ),
        ),
        migrations.RunPython(swap_legacy_dates, swap_legacy_dates),
        migrations.RunPython(remove_identical_checklist_duplicates, migrations.RunPython.noop),
        *[
            migrations.AlterField(
                model_name=model_name.lower(), name='created',
                field=models.DateTimeField(auto_now_add=True),
            )
            for model_name in DATE_MODELS
        ],
        *[
            migrations.AlterField(
                model_name=model_name.lower(), name='updated',
                field=models.DateTimeField(auto_now=True),
            )
            for model_name in DATE_MODELS
        ],
    ]
