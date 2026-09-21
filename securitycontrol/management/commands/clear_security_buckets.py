from django.core.management.base import BaseCommand
from django.utils import timezone
from securitycontrol.models import RateLimitBucket


class Command(BaseCommand):
    help = 'Delete expired login rate-limit buckets (schedule daily).'

    def handle(self, **options):
        count, _ = RateLimitBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Expired buckets deleted: {count}')
