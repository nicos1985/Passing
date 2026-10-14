from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0002_alter_adminnotification_action_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InboxNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=32)),
                ('source_id', models.BigIntegerField()),
                ('event', models.CharField(max_length=24)),
                ('title', models.CharField(max_length=120)),
                ('target_path', models.CharField(blank=True, max_length=240)),
                ('channels', models.CharField(blank=True, max_length=32)),
                ('viewed', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inbox_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddConstraint(
            model_name='inboxnotification',
            constraint=models.UniqueConstraint(fields=('user', 'category', 'source_id', 'event'), name='inbox_notification_once'),
        ),
    ]
