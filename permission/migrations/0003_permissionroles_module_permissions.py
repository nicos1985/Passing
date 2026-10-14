from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('permission', '0002_alter_contrapermission_contra_id_and_more')]

    operations = [
        migrations.AddField(
            model_name='permissionroles',
            name='module_permissions',
            field=models.JSONField(blank=True, default=list, verbose_name='Acceso a módulos'),
        ),
    ]
