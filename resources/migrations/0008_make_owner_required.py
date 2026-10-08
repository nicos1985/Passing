from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def set_owner_for_existing(apps, schema_editor):
    # Resolve user model from settings.AUTH_USER_MODEL (e.g. 'login.CustomUser')
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    try:
        User = apps.get_model(app_label, model_name)
    except Exception:
        User = None

    Info = apps.get_model('resources', 'InformationAssets')
    Vendor = apps.get_model('resources', 'Vendor')
    Project = apps.get_model('resources', 'Project')
    ClientCompany = apps.get_model('resources', 'ClientCompany')

    models_with_missing_owner = [
        model for model in (Info, Vendor, Project, ClientCompany)
        if model.objects.filter(owner__isnull=True).exists()
    ]
    if not models_with_missing_owner:
        return

    default_user = None
    if User is not None:
        default_user = User.objects.first()
        if default_user is None:
            # Try to create a minimal placeholder user; fall back to None if creation fails
            try:
                default_user = User.objects.create(username='owner_auto')
            except Exception:
                default_user = None

    # If we couldn't resolve/create a user, we will skip assigning and leave as NULL
    # The AlterField will fail if NULL remains; it's expected that the project has a user.
    if default_user is not None:
        for Model in (Info, Vendor, Project, ClientCompany):
            Model.objects.filter(owner__isnull=True).update(owner=default_user.pk)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    # The data step can insert into the shared user table; commit it before
    # changing tenant FKs to that table to avoid pending PostgreSQL triggers.
    atomic = False

    dependencies = [
        ('resources', '0007_alter_clientcompany_owner_and_more'),
    ]

    operations = [
        migrations.RunPython(set_owner_for_existing, noop_reverse),
        migrations.AlterField(
            model_name='informationassets',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_informationassets', related_query_name='owned_informationassets', to=settings.AUTH_USER_MODEL, verbose_name='Propietario'),
        ),
        migrations.AlterField(
            model_name='vendor',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_vendor', related_query_name='owned_vendor', to=settings.AUTH_USER_MODEL, verbose_name='Propietario'),
        ),
        migrations.AlterField(
            model_name='project',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_project', related_query_name='owned_project', to=settings.AUTH_USER_MODEL, verbose_name='Propietario'),
        ),
        migrations.AlterField(
            model_name='clientcompany',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_clientcompany', related_query_name='owned_clientcompany', to=settings.AUTH_USER_MODEL, verbose_name='Propietario'),
        ),
    ]
