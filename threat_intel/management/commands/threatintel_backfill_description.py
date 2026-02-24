from django.core.management.base import BaseCommand
from django.db import transaction

from threat_intel.models import Run, IntelItem
from threat_intel.services.normalize_text import extract_text_and_refs


class Command(BaseCommand):
    help = "Backfill IntelItem.description/references from payload when empty."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", type=int, default=None)
        parser.add_argument("--limit", type=int, default=0, help="0 = no limit")

    def handle(self, *args, **opts):
        run = Run.objects.get(id=opts["run_id"]) if opts["run_id"] else Run.objects.latest("started_at")

        qs = IntelItem.objects.filter(runitem__run=run).distinct()
        qs = qs.filter(description__isnull=True) | qs.filter(description="")

        if opts["limit"]:
            qs = qs[: opts["limit"]]

        to_update = []
        for it in qs.iterator(chunk_size=1000):
            desc, refs = extract_text_and_refs(it.payload or {})
            if desc:
                it.description = desc
            if refs and hasattr(it, "references"):
                it.references = refs
            if desc or refs:
                to_update.append(it)

        if not to_update:
            self.stdout.write("Nothing to backfill.")
            return

        fields = ["description"]
        if hasattr(IntelItem, "references"):
            fields.append("references")

        with transaction.atomic():
            IntelItem.objects.bulk_update(to_update, fields, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Backfilled {len(to_update)} IntelItems for run={run.id}"))
