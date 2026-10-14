from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('supporthub', '0003_telegram_preferences_and_events')]

    operations = [
        migrations.AddField(model_name='telegramrecipient', name='notify_risks', field=models.BooleanField(default=False)),
        migrations.AlterField(
            model_name='telegrameventdelivery', name='category',
            field=models.CharField(choices=[('monitoring', 'Monitorización'), ('password_request', 'Solicitud de acceso'), ('risk_assistant', 'Asistente de riesgos')], max_length=24),
        ),
    ]
