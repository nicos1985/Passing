from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from threat_intel.management.commands.threatintel_seed import Command as SeedCommand


class Command(BaseCommand):
    help = "Seed Threat Intel sources and TechTags for every tenant schema"

    def add_arguments(self, parser):
        parser.add_argument("--with-fortinet", action="store_true")
        parser.add_argument("--reset-keywords", action="store_true")
        parser.add_argument(
            "--schemas",
            type=str,
            default="",
            help="Comma-separated list of schemas to seed (optional)",
        )

    def handle(self, *args, **opts):
        with_fortinet = opts["with_fortinet"]
        reset_keywords = opts["reset_keywords"]
        requested = [s.strip() for s in (opts["schemas"] or "").split(",") if s.strip()]

        Tenant = get_tenant_model()
        tenants = Tenant.objects.all().order_by("schema_name")

        seed_cmd = SeedCommand()

        for t in tenants:
            schema_name = getattr(t, "schema_name", None)
            if not schema_name:
                continue
            # EXCLUIR PUBLIC: threat_intel es TENANT_APP, no existe en public
            if schema_name == "public":
                self.stdout.write("Skipping schema: public (TENANT_APP)")
                continue

            if requested and schema_name not in requested:
                continue

            self.stdout.write(f"Seeding tenant schema: {schema_name}")
            with schema_context(schema_name):
                seed_cmd.handle(
                    with_fortinet=with_fortinet,
                    reset_keywords=reset_keywords,
                )

        self.stdout.write(self.style.SUCCESS("Seed completed for tenant schemas."))
