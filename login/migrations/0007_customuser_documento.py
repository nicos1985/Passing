# Generated by Django 4.2.6 on 2024-07-08 14:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0006_customuser_birth_date_customuser_departure_motive_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='documento',
            field=models.CharField(blank=True, max_length=8, null=True, verbose_name='documento'),
        ),
    ]
