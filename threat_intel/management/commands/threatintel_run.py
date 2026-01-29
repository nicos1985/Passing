# threat_intel/management/commands/threatintel_run.py
from __future__ import annotations

from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timezone as dt_timezone

from threat_intel.models import Run, Source, RawItem, IntelItem, RunItem, SourceState, Report, TechTag
from threat_intel.sources.nvd import NvdConnector
from threat_intel.sources.aws_bulletins import AwsBulletinsConnector
# from threat_intel.sources.fortinet_psirt import FortinetPsirtConnector

from threat_intel.services.normalize import upsert_intel_item_from_raw
from threat_intel.services.relevance import mark_relevance_for_run
from threat_intel.services.report import build_report_for_run
from threat_intel.services.emailer import send_report_email
from threat_intel.services.ai import analyze_relevant_items_for_run

CONNECTOR_MAP = {
    "NVD": NvdConnector,
    "AWS": AwsBulletinsConnector,
    # "FORTINET": FortinetPsirtConnector,
}

def ensure_aware(dt):
    if dt is None:
        return None
    # Si ya es aware, devolvemos tal cual
    if timezone.is_aware(dt):
        return dt
    # Si es naive, asumimos UTC (para feeds externos)
    return timezone.make_aware(dt, dt_timezone.utc)


class Command(BaseCommand):
    help = "Run monthly/ad-hoc threat intelligence pipeline"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Lookback window in days (default from settings)")
        parser.add_argument("--send-email", action="store_true", help="Send report email")
        parser.add_argument("--adhoc", action="store_true", help="Run as ad-hoc instead of monthly")
        parser.add_argument("--dry-run", action="store_true", help="Fetch/normalize but do not send email")

    def handle(self, *args, **opts):
        cfg = getattr(settings, "THREAT_INTEL", {})
        days = opts["days"] or cfg.get("DEFAULT_DAYS", 30)

        end_dt = timezone.now()
        
        start_dt = end_dt - timedelta(days=days)

        run_type = "adhoc" if opts["adhoc"] else "monthly"
        # Crear registro de corrida
        run = Run.objects.create(
            run_type=run_type,
            period_start=start_dt,
            period_end=end_dt,
            status="running",
        )
        
        try:
            enabled = cfg.get("ENABLED_SOURCES", [])
            if not enabled:
                raise RuntimeError("No enabled sources. Set THREAT_INTEL['ENABLED_SOURCES'].")

            fetched_total = 0
            normalized_total = 0

            # 1) Ingest raw items
            for code in enabled:

                connector_cls = CONNECTOR_MAP.get(code)
                if not connector_cls:
                    self.stderr.write(self.style.WARNING(f"Unknown source code '{code}', skipping."))
                    continue

                source = Source.objects.filter(code=code, is_active=True).first()
                if not source:
                    self.stderr.write(self.style.WARNING(f"Source '{code}' not found/active in DB, skipping."))
                    continue

                state, _ = SourceState.objects.get_or_create(source=source)
                connector = connector_cls()
                try:
                    items, new_cursor = connector.fetch(start_dt, end_dt, cursor=state.cursor or None)
                except Exception as e:
                    print(f"Error fetching from source {code}: {e}")
                    continue

                fetched_total += len(items)

                for it in items:
                    published_at = ensure_aware(it.get("published_at"))
                    RawItem.objects.update_or_create(
                        source=source,
                        external_id=it["external_id"],
                        defaults={
                            "published_at": published_at,
                            "url": it["url"],
                            "title": it.get("title") or "",
                            "raw_payload": it.get("payload") or {},
                            "fetched_at": timezone.now(),
                        },
                    )

                state.cursor = new_cursor or {}
                state.last_successful_run_at = timezone.now()
                state.save(update_fields=["cursor", "last_successful_run_at"])

            run.fetched_count = fetched_total
            run.save(update_fields=["fetched_count"])

            # 2) Normalize + dedupe into IntelItem and link to run (RunItem)
            raw_qs = RawItem.objects.filter(
                fetched_at__gte=run.started_at  # lo ingresado en esta corrida
            ).select_related("source")

            with transaction.atomic():
                for raw in raw_qs:
                    item = upsert_intel_item_from_raw(raw)
                    RunItem.objects.get_or_create(run=run, item=item)
                    normalized_total += 1

            run.normalized_count = normalized_total
            run.save(update_fields=["normalized_count"])

            # 3) Apply relevance rules (match stack tags)
            total_items, relevant_items, updated_items = mark_relevance_for_run(run)
            self.stdout.write(self.style.SUCCESS(
                f"Relevance computed: items={total_items} relevant={relevant_items} updated={updated_items}"
            ))

            run.relevant_count = relevant_items
            run.save(update_fields=["relevant_count"])
            self.stdout.write(f"AI enabled? {cfg.get('ENABLE_AI_ANALYSIS', False)} model={cfg.get('OPENAI_MODEL')}")


            # 4) (Optional) AI analysis — lo dejamos preparado, pero apagado al inicio
            if cfg.get("ENABLE_AI_ANALYSIS", False):
                try:
                    print("Starting AI analysis for relevant items...")
                    analyzed = analyze_relevant_items_for_run(run)
                    
                    self.stdout.write(self.style.SUCCESS(f"AI analysis created for {analyzed} items"))
                except Exception as e:
                    import traceback
                    self.stderr.write(self.style.WARNING("AI analysis failed. Details:"))
                    self.stderr.write(traceback.format_exc())


            # 5) Build report + persist
            subject, body_md, body_html = build_report_for_run(run)
            recipients = cfg.get("EMAIL_RECIPIENTS", [])

            report, _ = Report.objects.update_or_create(
                run=run,
                defaults={
                    "subject": subject,
                    "body_md": body_md,
                    "body_html": body_html or "",
                    "recipients": recipients,
                },
            )

            # 6) Send email if requested
            if opts["send_email"] and not opts["dry_run"]:
                send_report_email(report)
                report.sent_at = timezone.now()
                report.save(update_fields=["sent_at"])

            run.status = "success"
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "finished_at"])
            
            end_ts = run.finished_at or timezone.now()
            fetched_count = RawItem.objects.filter(
                fetched_at__gte=run.started_at,
                fetched_at__lte=end_ts,
            ).count()
            normalized_count = RunItem.objects.filter(run=run).count()
            relevant_count = IntelItem.objects.filter(runitem__run=run, is_relevant=True).distinct().count()

            self.stdout.write(self.style.SUCCESS(
                    f"Threat intel run success: fetched={fetched_count} normalized={normalized_count} relevant={relevant_count}"
                ))

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error", "finished_at"])
            raise
