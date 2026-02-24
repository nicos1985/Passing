from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django_tenants.utils import get_tenant_model, schema_context
from django.utils import timezone

from accounts.models import TenantSettings
from resources.models import VendorEvaluation, VendorEvaluationStatus


class Command(BaseCommand):
    help = "Send reminder emails to owners with pending vendor evaluations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schemas",
            type=str,
            default="",
            help="Optional comma-separated list of tenant schemas to process",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only log which reminders would be sent without emailing",
        )

    def handle(self, *args, **options):
        requested = [s.strip() for s in (options.get("schemas") or "").split(",") if s.strip()]
        dry_run = options.get("dry_run", False)

        Tenant = get_tenant_model()
        tenants = Tenant.objects.exclude(schema_name="public").order_by("schema_name")

        for tenant in tenants:
            schema_name = getattr(tenant, "schema_name", None)
            if not schema_name or (requested and schema_name not in requested):
                continue
            self.stdout.write(f"Processing tenant schema: {schema_name}")
            with schema_context(schema_name):
                self._process_tenant(tenant, dry_run)

        self.stdout.write(self.style.SUCCESS("Pending evaluation reminders executed."))

    def _process_tenant(self, tenant, dry_run):
        settings_obj = getattr(tenant, "settings", None)
        if settings_obj is None:
            settings_obj = TenantSettings.for_client(getattr(tenant, "id", None))
        reminder_days = getattr(settings_obj, "reminder_lead_days", 14)
        due_date = timezone.localdate() + timedelta(days=reminder_days)

        pending = (
            VendorEvaluation.objects
            .filter(
                status=VendorEvaluationStatus.PENDING,
                scheduled_date__isnull=False,
                scheduled_date__lte=due_date,
                reminder_sent_at__isnull=True,
                vendor__owner__isnull=False,
            )
            .select_related('vendor', 'vendor__owner')
        )

        if not pending:
            self.stdout.write(f"  No hay evaluaciones pendientes para los próximos {reminder_days} días.")
            return

        sender = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost")
        tenant_host = getattr(settings, "TENANT_BASE_URL", "localhost:8000")

        for evaluation in pending:
            owner = evaluation.vendor.owner
            if not owner or not owner.email:
                continue

            url = f"http://{tenant.schema_name}.{tenant_host}/resources/vendor-evaluation/{evaluation.pk}/"
            subject = f"Recordatorio: evaluación de proveedor {evaluation.vendor.name}"
            message = (
                f"Hola {owner.get_full_name() or owner.email},\n\n"
                f"La evaluación del proveedor {evaluation.vendor.name} está programada para {evaluation.scheduled_date}.\n"
                f"Podés completarla en: {url}\n\n"
                "Gracias,\nEquipo de seguridad"
            )

            if dry_run:
                self.stdout.write(f"  [dry-run] Recordatorio para {owner.email} -> {url}")
            else:
                try:
                    send_mail(subject, message, sender, [owner.email], fail_silently=False)
                    self.stdout.write(f"  Recordatorio enviado a {owner.email} para evaluación {evaluation.pk}")
                except Exception as exc:
                    self.stderr.write(f"  Error al enviar recordatorio a {owner.email}: {exc}")
                    continue

            evaluation.reminder_sent_at = timezone.now()
            evaluation.save(update_fields=['reminder_sent_at'])
*** End File