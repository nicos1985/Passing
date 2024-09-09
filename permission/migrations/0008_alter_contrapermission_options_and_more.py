# Generated by Django 4.1.4 on 2024-09-08 22:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permission', '0007_permissionroles_is_active'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='contrapermission',
            options={'verbose_name': 'Permiso', 'verbose_name_plural': 'Permisos'},
        ),
        migrations.AlterField(
            model_name='contrapermission',
            name='permission',
            field=models.CharField(blank=True, default='vacio', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='permissionroles',
            name='comment',
            field=models.CharField(blank=True, default='vacio', max_length=200),
            preserve_default=False,
        ),
    ]