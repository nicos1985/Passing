# Generated by Django 4.1.4 on 2024-05-05 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('passbase', '0006_alter_contrasena_actualizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrasena',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='contra_files/'),
        ),
    ]
