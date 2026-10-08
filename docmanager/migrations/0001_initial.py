# Generated manually for docmanager initial models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Nombre visible')),
                ('service', models.CharField(choices=[('google_drive', 'Google Drive')], default='google_drive', max_length=64)),
                ('status', models.CharField(choices=[('active', 'Activa'), ('inactive', 'Inactiva'), ('revoked', 'Revocada')], default='active', max_length=32)),
                ('key_id', models.CharField(blank=True, max_length=128, verbose_name='Identificador interno')),
                ('secret_encrypted', models.TextField(verbose_name='Secreto cifrado')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='integration_credentials', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
            ],
            options={
                'verbose_name': 'Credencial de integración',
                'verbose_name_plural': 'Credenciales de integración',
                'ordering': ('-updated_at', '-id'),
            },
        ),
        migrations.CreateModel(
            name='DocumentoControlado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('drive_file_id', models.CharField(max_length=255, unique=True, verbose_name='ID de Drive')),
                ('carpeta_drive_id', models.CharField(blank=True, max_length=255, verbose_name='Carpeta Drive')),
                ('nombre_archivo', models.CharField(max_length=255, verbose_name='Nombre en Drive')),
                ('link_edicion', models.URLField(verbose_name='Link de edición')),
                ('ultima_sincronizacion', models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización')),
                ('fecha_modificacion_drive', models.DateTimeField(blank=True, null=True, verbose_name='Modificado en Drive')),
                ('ultimo_editor_drive', models.CharField(blank=True, max_length=255, verbose_name='Último editor')),
                ('frecuencia_revision_dias', models.PositiveIntegerField(default=90, verbose_name='Frecuencia de revisión (días)')),
                ('no_encontrado', models.BooleanField(default=False, verbose_name='No encontrado en Drive')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado')),
                ('credencial', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos', to='docmanager.integrationcredential', verbose_name='Credencial de servicio')),
            ],
            options={
                'verbose_name': 'Documento controlado',
                'verbose_name_plural': 'Documentos controlados',
                'ordering': ('-fecha_modificacion_drive', '-updated_at'),
            },
        ),
    ]
