# Generated by Django 4.1.4 on 2024-07-21 00:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('passbase', '0011_alter_logdata_detail_alter_logdata_password'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contrasena',
            name='contraseña',
            field=models.BinaryField(),
        ),
    ]
