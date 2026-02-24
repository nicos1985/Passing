from django.core.management.base import BaseCommand
from accounts.models import TwoFAChange


class Command(BaseCommand):
    help = 'Muestra los cambios recientes de is_2fa_enabled (últimos 200)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        limit = options.get('limit')
        qs = TwoFAChange.objects.select_related('user').all()[:limit]
        total = TwoFAChange.objects.count()
        if total == 0:
            self.stdout.write('No se encontraron eventos TwoFAChange')
            return
        self.stdout.write(f'Found {total} TwoFAChange events (showing up to {limit})')
        for e in qs:
            who = e.user.email if e.user else f'user_id={getattr(e, "user_id", None)}'
            self.stdout.write(f"{e.at.isoformat()} - {who} : {e.old_value} -> {e.new_value} source={e.source} meta={e.meta}")
