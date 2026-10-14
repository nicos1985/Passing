from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('supporthub', '0002_telegrambotconfig'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='telegramrecipient', name='notify_support', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='telegramrecipient', name='notify_monitoring', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='telegramrecipient', name='notify_password_requests', field=models.BooleanField(default=False)),
        migrations.CreateModel(name='TelegramPairing', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('pending_chat_id', models.BigIntegerField()),
            ('code_hash', models.CharField(max_length=64)),
            ('expires_at', models.DateTimeField()),
            ('attempts', models.PositiveSmallIntegerField(default=0)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='TelegramEventDelivery', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('category', models.CharField(choices=[('monitoring', 'Monitorización'), ('password_request', 'Solicitud de acceso')], max_length=24)),
            ('source_id', models.BigIntegerField()),
            ('event', models.CharField(default='opened', max_length=12)),
            ('status', models.CharField(choices=[('pending', 'Pendiente'), ('sent', 'Enviado'), ('failed', 'Falló'), ('cancelled', 'Cancelado')], default='pending', max_length=12)),
            ('attempts', models.PositiveSmallIntegerField(default=0)),
            ('next_attempt_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ('last_error', models.CharField(blank=True, max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('sent_at', models.DateTimeField(blank=True, null=True)),
            ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='supporthub.telegramrecipient')),
        ], options={'constraints': [models.UniqueConstraint(fields=('recipient', 'category', 'source_id', 'event'), name='telegram_event_delivery_once')]}),
    ]
