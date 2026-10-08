import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, close_old_connections
from django.utils import timezone
from django_tenants.utils import get_tenant_model, tenant_context

from monitoring.deliveries import deliver_pending, sync_bitrix_resolutions
from monitoring.models import Monitor, WorkerHeartbeat
from monitoring.retention import compact_history
from monitoring.services import execute_monitor


LOCK_ID = 174050


def _execute_for_tenant(tenant, monitor_id):
    close_old_connections()
    try:
        with tenant_context(tenant):
            execute_monitor(monitor_id)
    finally:
        connection.close()


class Command(BaseCommand):
    help = "Ejecuta los chequeos de monitorización de todos los tenants. Iniciar una sola instancia con systemd."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Ejecutar un ciclo y salir")

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_ID])
            if not cursor.fetchone()[0]:
                raise CommandError("Ya hay un worker de monitorización activo")
        last_compaction_date = None
        try:
            while True:
                now = timezone.now()
                for tenant in get_tenant_model().objects.exclude(schema_name="public"):
                    with tenant_context(tenant):
                        due = list(Monitor.objects.filter(enabled=True, next_check_at__lte=now).values_list("pk", flat=True)[:50])
                        with ThreadPoolExecutor(max_workers=10) as pool:
                            jobs = {pool.submit(_execute_for_tenant, tenant, monitor_id): monitor_id for monitor_id in due}
                            for job in as_completed(jobs):
                                try:
                                    job.result()
                                except Exception as exc:
                                    self.stderr.write(f"Error en monitor {jobs[job]}: {type(exc).__name__}")
                        deliver_pending()
                        sync_bitrix_resolutions()
                        if last_compaction_date != now.date():
                            compact_history()
                        WorkerHeartbeat.objects.update_or_create(
                            pk=1, defaults={"last_cycle_at": timezone.now()}
                        )
                last_compaction_date = now.date()
                if options["once"]:
                    break
                time.sleep(5)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_ID])
