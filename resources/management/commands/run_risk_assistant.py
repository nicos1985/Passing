"""Ejecuta el análisis diario de riesgos para todos los tenants."""

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, tenant_context

from resources.risk_assistant import run_daily


class Command(BaseCommand):
    help = 'Genera las sugerencias de riesgos del día. Es idempotente por tenant y fecha.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='Schema de un único tenant, por ejemplo empresa1.')
        parser.add_argument('--force', action='store_true', help='Reanaliza el día actual aunque ya se haya completado.')
        parser.add_argument('--rules-only', action='store_true', help='Usa solo reglas locales, sin llamar a la IA externa.')

    def handle(self, *args, **options):
        tenants = get_tenant_model().objects.exclude(schema_name='public')
        if options['tenant']:
            tenants = tenants.filter(schema_name=options['tenant'])
            if not tenants.exists():
                raise CommandError('No existe ese tenant.')
        for tenant in tenants:
            with tenant_context(tenant):
                run = run_daily(force=options['force'], use_ai=not options['rules_only'])
                self.stdout.write(f'{tenant.schema_name}: {run.day} {run.status}, {run.created_count} nuevas hoy')
