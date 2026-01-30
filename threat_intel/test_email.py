#!/usr/bin/env python
"""
Email service testing script.
Run from Django shell: python manage.py shell < threat_intel/test_email.py
"""

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

print("=" * 70)
print("THREAT INTEL EMAIL SERVICE TEST")
print("=" * 70)

# Get a sample report
try:
    report = Report.objects.first()
    if not report:
        print("\n❌ No reports found. Create a report first.")
        exit(1)
    
    print(f"\n✓ Using report: #{report.id} - {report.subject}")
    print(f"  Recipients: {report.recipients or 'None configured'}")
    
except Exception as e:
    print(f"\n❌ Error loading report: {e}")
    exit(1)

# Test 1: Generate Markdown
print("\n" + "=" * 70)
print("TEST 1: Generate Markdown Report")
print("=" * 70)
try:
    filename, content = generate_report_markdown(report)
    print(f"✓ Generated: {filename}")
    print(f"  Size: {len(content)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Generate JSON
print("\n" + "=" * 70)
print("TEST 2: Generate JSON Report")
print("=" * 70)
try:
    filename, content = generate_report_json(report)
    print(f"✓ Generated: {filename}")
    print(f"  Size: {len(content)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Generate PDF (if WeasyPrint installed)
print("\n" + "=" * 70)
print("TEST 3: Generate PDF Report (Requires WeasyPrint)")
print("=" * 70)
try:
    filename, content = generate_report_pdf(report)
    print(f"✓ Generated: {filename}")
    print(f"  Size: {len(content)} bytes")
except ImportError:
    print("⚠ WeasyPrint not installed. Install with: pip install weasyprint")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Send via SMTP (without email)
print("\n" + "=" * 70)
print("TEST 4: Send via SMTP (Test - No Email)")
print("=" * 70)
if report.recipients:
    try:
        # Just print what would be sent
        print(f"✓ Would send via SMTP to:")
        for recipient in report.recipients:
            print(f"    - {recipient}")
        print(f"\nSubject: {report.subject}")
        print(f"Body: {report.body_md[:100]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("⚠ No recipients configured. Skipping.")

# Test 5: Test Brevo configuration
print("\n" + "=" * 70)
print("TEST 5: Check Brevo Configuration")
print("=" * 70)
from django.conf import settings

brevo_key = getattr(settings, 'BREVO_API_KEY', None)
backend = getattr(settings, 'THREAT_INTEL_EMAIL_BACKEND', 'smtp')

print(f"Email Backend: {backend}")
print(f"Brevo API Key: {'✓ Configured' if brevo_key else '❌ Not configured'}")

if not brevo_key:
    print("\nTo use Brevo:")
    print("  1. Install SDK: pip install sib-api-v3-sdk")
    print("  2. Add to settings.py or environment:")
    print("     BREVO_API_KEY = 'xkeysib-...'")
    print("     THREAT_INTEL_EMAIL_BACKEND = 'brevo'")

# Test 6: Full test with attachments (simulation)
print("\n" + "=" * 70)
print("TEST 6: Prepare Email with Attachments (Simulation)")
print("=" * 70)
if report.recipients:
    try:
        attachments = []
        
        # Add Markdown
        md_file, md_content = generate_report_markdown(report)
        attachments.append((md_file, md_content, "text/markdown"))
        print(f"✓ Added: {md_file}")
        
        # Add JSON
        json_file, json_content = generate_report_json(report)
        attachments.append((json_file, json_content, "application/json"))
        print(f"✓ Added: {json_file}")
        
        # Try PDF
        try:
            pdf_file, pdf_content = generate_report_pdf(report)
            attachments.append((pdf_file, pdf_content, "application/pdf"))
            print(f"✓ Added: {pdf_file}")
        except ImportError:
            print("⚠ PDF skipped (WeasyPrint not installed)")
        
        print(f"\nTotal attachments: {len(attachments)}")
        print("Total size: {:.2f} MB".format(sum(len(content) for _, content, _ in attachments) / 1024 / 1024))
        
        # Show what send_report_email would do
        print("\n✓ Ready to send with:")
        print(f"  - Recipients: {', '.join(report.recipients)}")
        print(f"  - Attachments: {len(attachments)} files")
        print(f"  - Backend: {backend}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("⚠ No recipients configured. Skipping.")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("\nTo actually send an email, use:")
print("  from threat_intel.services.emailer import send_report_email")
print("  result = send_report_email(report, attachments=[...], use_brevo=False)")
print("\nOr use the web UI: /threat-intel/reports/<id>/ → 'Enviar por Email'")
print("=" * 70)
