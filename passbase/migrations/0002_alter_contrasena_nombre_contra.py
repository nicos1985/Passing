# Generated by Django 4.1.4 on 2023-10-16 03:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('passbase', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contrasena',
            name='nombre_contra',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
