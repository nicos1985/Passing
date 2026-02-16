#!/usr/bin/env python
"""
Email service testing script.
Run from Django shell: python manage.py shell < threat_intel/test_email.py
"""

import logging
from threat_intel.models import Report, Run
from threat_intel.services.emailer import (
    send_report_email, 
    send_report_email_smtp, 
    send_report_email_brevo
)
from threat_intel.services.report_generator import (
    generate_report_pdf,
    generate_report_markdown,
    generate_report_json
)

logger = logging.getLogger(__name__)
logger.info("%s", "=" * 70)
logger.info("THREAT INTEL EMAIL SERVICE TEST")
logger.info("%s", "=" * 70)

# Get a sample report
try:
    report = Report.objects.first()
    if not report:
        logger.error("No reports found. Create a report first.")
        exit(1)

    logger.info("Using report: #%(id)s - %(subj)s", {"id": report.id, "subj": report.subject})
    logger.info("Recipients: %s", (report.recipients or 'None configured'))
    
except Exception as e:
    logger.exception("Error loading report")
    exit(1)

# Test 1: Generate Markdown
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 1: Generate Markdown Report")
logger.info("%s", "=" * 70)
try:
    filename, content = generate_report_markdown(report)
    logger.info("Generated: %s", filename)
    logger.info("Size: %d bytes", len(content))
except Exception as e:
    logger.exception("Error generating markdown report")

# Test 2: Generate JSON
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 2: Generate JSON Report")
logger.info("%s", "=" * 70)
try:
    filename, content = generate_report_json(report)
    logger.info("Generated: %s", filename)
    logger.info("Size: %d bytes", len(content))
except Exception as e:
    logger.exception("Error generating JSON report")

# Test 3: Generate PDF (if WeasyPrint installed)
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 3: Generate PDF Report (Requires WeasyPrint)")
logger.info("%s", "=" * 70)
try:
    filename, content = generate_report_pdf(report)
    logger.info("Generated: %s", filename)
    logger.info("Size: %d bytes", len(content))
except ImportError:
    logger.warning("WeasyPrint not installed. Install with: pip install weasyprint")
except Exception as e:
    logger.exception("Error generating PDF report")

# Test 4: Send via SMTP (without email)
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 4: Send via SMTP (Test - No Email)")
logger.info("%s", "=" * 70)
if report.recipients:
    try:
        # Just log what would be sent
        logger.info("Would send via SMTP to:")
        for recipient in report.recipients:
            logger.info("    - %s", recipient)
        logger.info("Subject: %s", report.subject)
        logger.info("Body: %.100s...", report.body_md)
    except Exception as e:
        logger.exception("Error during SMTP test output")
else:
    logger.warning("No recipients configured. Skipping.")

# Test 5: Test Brevo configuration
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 5: Check Brevo Configuration")
logger.info("%s", "=" * 70)
from django.conf import settings

brevo_key = getattr(settings, 'BREVO_API_KEY', None)
backend = getattr(settings, 'THREAT_INTEL_EMAIL_BACKEND', 'smtp')

logger.info("Email Backend: %s", backend)
logger.info("Brevo API Key: %s", ('✓ Configured' if brevo_key else '❌ Not configured'))

if not brevo_key:
if not brevo_key:
    logger.info("To use Brevo:")
    logger.info("  1. Install SDK: pip install sib-api-v3-sdk")
    logger.info("  2. Add to settings.py or environment:")
    logger.info("     BREVO_API_KEY = 'xkeysib-...' ")
    logger.info("     THREAT_INTEL_EMAIL_BACKEND = 'brevo'")

# Test 6: Full test with attachments (simulation)
logger.info("%s", "\n" + "=" * 70)
logger.info("TEST 6: Prepare Email with Attachments (Simulation)")
logger.info("%s", "=" * 70)

if report.recipients:
    try:
        attachments = []
        
        # Add Markdown
        md_file, md_content = generate_report_markdown(report)
        attachments.append((md_file, md_content, "text/markdown"))
        logger.info("Added: %s", md_file)
        
        # Add JSON
        json_file, json_content = generate_report_json(report)
        attachments.append((json_file, json_content, "application/json"))
        logger.info("Added: %s", json_file)
        
        # Try PDF
        try:
            pdf_file, pdf_content = generate_report_pdf(report)
            attachments.append((pdf_file, pdf_content, "application/pdf"))
            logger.info("Added: %s", pdf_file)
        except ImportError:
            logger.warning("PDF skipped (WeasyPrint not installed)")
        
        logger.info("Total attachments: %d", len(attachments))
        logger.info("Total size: %.2f MB", sum(len(content) for _, content, _ in attachments) / 1024 / 1024)
        
        # Show what send_report_email would do
        logger.info("Ready to send with:")
        logger.info("  - Recipients: %s", ', '.join(report.recipients))
        logger.info("  - Attachments: %d files", len(attachments))
        logger.info("  - Backend: %s", backend)
        
    except Exception as e:
        logger.exception("Error preparing attachments or sending preview")
else:
    logger.warning("No recipients configured. Skipping.")

logger.info("%s", "\n" + "=" * 70)
logger.info("TEST COMPLETE")
logger.info("%s", "=" * 70)
logger.info("To actually send an email, use:")
logger.info("  from threat_intel.services.emailer import send_report_email")
logger.info("  result = send_report_email(report, attachments=[...], use_brevo=False)")
logger.info("Or use the web UI: /threat-intel/reports/<id>/ → 'Enviar por Email'")
logger.info("%s", "=" * 70)
