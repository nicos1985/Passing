"""Worker único para consultar Bitrix24 y enviar avisos de soporte."""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from django_tenants.utils import get_tenant_model, tenant_context

from supporthub.models import BitrixPortal
from supporthub.services import dispatch_notices, poll_portal, purge_old_history
from supporthub.telegram_events import dispatch_event_deliveries
from resources.risk_assistant import run_due as run_risk_assistant_due


LOCK_ID = 174061


class Command(BaseCommand):
    help = 'Consulta los grupos de soporte y entrega avisos a Telegram. Ejecutar una sola instancia.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Ejecutar un ciclo y salir')

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [LOCK_ID])
            if not cursor.fetchone()[0]:
                raise CommandError('Ya hay un worker de soporte activo.')
        last_cleanup = None
        try:
            while True:
                today = timezone.localdate()
                for tenant in get_tenant_model().objects.exclude(schema_name='public'):
                    with tenant_context(tenant):
                        try:
                            run_risk_assistant_due()
                        except Exception as exc:
                            self.stderr.write(f'{tenant.schema_name}: error en asistente de riesgos ({type(exc).__name__}).')
                        for portal in BitrixPortal.objects.filter(enabled=True):
                            try:
                                poll_portal(portal)
                            except Exception as exc:
                                # Nunca mostrar excepciones HTTP: pueden incluir el webhook secreto.
                                self.stderr.write(f'{tenant.schema_name}: error consultando portal {portal.pk} ({type(exc).__name__}).')
                        try:
                            dispatch_notices()
                        except Exception as exc:
                            self.stderr.write(f'{tenant.schema_name}: error entregando avisos de soporte ({type(exc).__name__}).')
                        try:
                            dispatch_event_deliveries()
                        except Exception as exc:
                            self.stderr.write(f'{tenant.schema_name}: error entregando avisos personales ({type(exc).__name__}).')
                        if last_cleanup != today:
                            try:
                                purge_old_history()
                            except Exception as exc:
                                self.stderr.write(f'{tenant.schema_name}: error limpiando historial ({type(exc).__name__}).')
                last_cleanup = today
                if options['once']:
                    break
                time.sleep(20)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [LOCK_ID])
