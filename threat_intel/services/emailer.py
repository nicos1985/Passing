# threat_intel/services/emailer.py
from __future__ import annotations
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from threat_intel.models import Report

def send_report_email(report: Report) -> None:
    recipients = report.recipients or []
    if not recipients:
        raise RuntimeError("No recipients configured for threat intel email.")

    msg = EmailMultiAlternatives(
        subject=report.subject,
        body=report.body_md,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=recipients,
    )
    if report.body_html:
        msg.attach_alternative(report.body_html, "text/html")
    msg.send()
