from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

class Command(BaseCommand):
    help = "Crea/actualiza el SocialApp de Google y lo asocia al SITE_ID actual."

    def add_arguments(self, parser):
        parser.add_argument("--client-id", required=True)
        parser.add_argument("--secret", required=True)
        parser.add_argument("--name", default="Google Passing")

    def handle(self, *args, **opts):
        client_id = opts["client_id"]
        secret = opts["secret"]
        name = opts["name"]

        app, created = SocialApp.objects.update_or_create(
            provider="google",
            defaults={"name": name, "client_id": client_id, "secret": secret},
        )
        site = Site.objects.get(pk=settings.SITE_ID)
        app.sites.set([site])   # <-- asociar al Site del hub
        app.save()

        self.stdout.write(self.style.SUCCESS(
            f"Google SocialApp {'creado' if created else 'actualizado'} y asociado a SITE_ID={settings.SITE_ID}"
        ))
