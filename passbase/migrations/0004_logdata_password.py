# Generated by Django 4.1.4 on 2023-11-18 15:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('passbase', '0003_contrasena_actualizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='logdata',
            name='password',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]