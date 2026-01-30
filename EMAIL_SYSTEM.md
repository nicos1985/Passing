# 📧 Threat Intelligence Email System

## Overview

The email service enables sending threat intelligence reports with **PDF attachments** via **SMTP (Gmail)** or **Brevo (SendinBlue) API**.

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃     Threat Intel Report Distribution System                  ┃
┃                                                               ┃
┃  ┌────────────────────────────────────────────────────┐   ┃
┃  │  1. Create Report (from Run)                        │   ┃
┃  │     - Subject, Markdown, Recipients                │   ┃
┃  └────────────┬─────────────────────────────────────┘   ┃
┃               │                                             ┃
┃  ┌────────────▼─────────────────────────────────────┐   ┃
┃  │  2. View/Edit Report                             │   ┃
┃  │     - Preview HTML/Markdown                       │   ┃
┃  │     - Show analyses & reviews                     │   ┃
┃  └────────────┬─────────────────────────────────────┘   ┃
┃               │                                             ┃
┃  ┌────────────▼─────────────────────────────────────┐   ┃
┃  │  3. Send Email (Modal)                           │   ┃
┃  │     □ Send email                                  │   ┃
┃  │     □ Include PDF attachment                      │   ┃
┃  │     ◉ SMTP    ○ Brevo                             │   ┃
┃  └────────────┬─────────────────────────────────────┘   ┃
┃               │                                             ┃
┃  ┌────────────▼─────────────────────────────────────┐   ┃
┃  │  4. Generate & Send                              │   ┃
┃  │     ├─ Generate PDF (if checked)                 │   ┃
┃  │     ├─ Format email body (HTML + Text)           │   ┃
┃  │     ├─ Route to SMTP or Brevo                    │   ┃
┃  │     └─ Mark report.sent_at = now()               │   ┃
┃  └────────────┬─────────────────────────────────────┘   ┃
┃               │                                             ┃
┃  ┌────────────▼─────────────────────────────────────┐   ┃
┃  │  5. Delivery                                      │   ┃
┃  │     ├─ SMTP → Gmail → Recipients                 │   ┃
┃  │     └─ Brevo → Brevo API → Recipients            │   ┃
┃  └─────────────────────────────────────────────────┘   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Key Features

### 📤 Email Backends
- **SMTP** (Default) - Gmail/Standard SMTP servers
  - Already configured
  - Works immediately
  
- **Brevo** (Optional) - SendinBlue transactional emails
  - Higher deliverability
  - Better tracking
  - Requires API key

### 📎 Attachment Support
- **PDF Reports** - HTML to PDF conversion
  - Requires: `pip install weasyprint`
  - Auto-generated filenames with timestamp
  - Styled with headers, footers, formatting
  
- **Alternative Formats**
  - Markdown export (.md)
  - JSON export (.json)
  - No additional dependencies

### 🎯 Email Features
- HTML + plain text email bodies
- Multiple recipients support
- Automatic sender configuration
- Base64 encoded attachments (Brevo)
- Error handling & logging
- Status tracking (sent_at timestamp)

---

## Technology Stack

```
Django 4.1.4
├─ EmailMultiAlternatives (SMTP)
│  └─ Gmail SMTP Server
│
├─ WeasyPrint (Optional - PDF generation)
│  └─ HTML → PDF conversion
│
└─ sib-api-v3-sdk (Optional - Brevo)
   └─ SendinBlue Transactional Email API
```

---

## File Structure

```
threat_intel/
├── services/
│   ├── emailer.py                 # Core email functions
│   │   ├── send_report_email()                [Main wrapper]
│   │   ├── send_report_email_smtp()           [SMTP backend]
│   │   └── send_report_email_brevo()          [Brevo backend]
│   │
│   └── report_generator.py        # Export utilities
│       ├── generate_report_pdf()               [HTML → PDF]
│       ├── generate_report_markdown()          [Markdown export]
│       └── generate_report_json()              [JSON export]
│
├── forms.py                       # Email forms
│   ├── ReportForm
│   └── ReportSendForm
│
├── views.py                       # Views
│   ├── ReportSendView()                       [Handles sending]
│   └── ReportDetailView()                     [Shows modal]
│
├── EMAIL_SETUP.md                 # Full documentation
├── test_email.py                  # Test script
└── models.py                      # Report model
   └── Report (with sent_at field)

templates/
└── threat_intel_report_detail.html # Send modal

passing/
└── settings.py                    # Email configuration
```

---

## Quick Start

### 1️⃣ Create a Report
```
Navigate: /threat-intel/runs/<run_id>/report/create/
- Fill: Subject, Body (Markdown), Recipients (comma-separated emails)
- Save
```

### 2️⃣ View Report
```
Navigate: /threat-intel/reports/<report_id>/
- See preview of HTML/Markdown
- See included analyses
- See recipients list
```

### 3️⃣ Send Report
```
Click: "Enviar por Email" button
Modal options:
  ☐ Send email (required to enable PDF)
  ☐ Include PDF attachment (requires WeasyPrint)
  ◉ Backend: SMTP / Brevo
Click: "Enviar Reporte"
```

### 4️⃣ Check Status
```
Report shows:
  - Badge: "Enviado" (green)
  - Timestamp: "Enviado: 2026-01-29 14:30:22"
  - Recipients: Email list
```

---

## Usage Examples

### Example 1: Send via SMTP (Gmail) - No PDF

```python
from threat_intel.models import Report
from threat_intel.services.emailer import send_report_email

report = Report.objects.get(id=1)
result = send_report_email(report)

if result['status'] == 'success':
    print(f"Email sent! {result['message']}")
else:
    print(f"Error: {result['message']}")
```

### Example 2: Send with PDF Attachment

```python
from threat_intel.services.emailer import send_report_email
from threat_intel.services.report_generator import generate_report_pdf

report = Report.objects.get(id=1)

# Generate PDF
filename, pdf_bytes = generate_report_pdf(report)

# Send with attachment
attachments = [(filename, pdf_bytes, "application/pdf")]
result = send_report_email(report, attachments=attachments)

print(f"✓ Sent PDF: {filename}")
```

### Example 3: Force Brevo Backend

```python
# Even if SMTP is configured, use Brevo
result = send_report_email(report, use_brevo=True)

if 'data' in result:
    message_id = result['data']['message_id']
    print(f"✓ Brevo Message ID: {message_id}")
```

### Example 4: Multiple Attachments

```python
from threat_intel.services.report_generator import (
    generate_report_pdf,
    generate_report_markdown,
    generate_report_json
)

report = Report.objects.get(id=1)

attachments = []

# Add PDF
pdf_file, pdf_content = generate_report_pdf(report)
attachments.append((pdf_file, pdf_content, "application/pdf"))

# Add Markdown
md_file, md_content = generate_report_markdown(report)
attachments.append((md_file, md_content, "text/markdown"))

# Add JSON
json_file, json_content = generate_report_json(report)
attachments.append((json_file, json_content, "application/json"))

# Send all
result = send_report_email(report, attachments=attachments)
print(f"✓ Sent {len(attachments)} attachments")
```

---

## Configuration

### Environment Variables

```bash
# Email backend
export THREAT_INTEL_EMAIL_BACKEND=smtp        # or "brevo"

# Brevo API (optional)
export BREVO_API_KEY=xkeysib-1234567890...
```

### Django Settings

```python
# passing/settings.py

# Email backend for reports
THREAT_INTEL_EMAIL_BACKEND = "smtp"  # or "brevo"

# Brevo API key (if using Brevo)
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# Sender name for Brevo
DEFAULT_FROM_NAME = "Threat Intel System"

# Current SMTP settings (Gmail)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "noreply@anima.bot"
EMAIL_HOST_PASSWORD = "..."
DEFAULT_FROM_EMAIL = "noreply@anima.bot"
```

---

## Installation

### Basic (SMTP - Already Included)
No additional packages needed! Uses Django's built-in EmailBackend.

### With PDF Support
```bash
pip install weasyprint
```

### With Brevo Support
```bash
pip install sib-api-v3-sdk
```

### All Features
```bash
pip install weasyprint sib-api-v3-sdk
```

---

## Testing

### Run Test Suite
```bash
python manage.py shell < threat_intel/test_email.py
```

This will:
- ✓ Load a sample report
- ✓ Test Markdown generation
- ✓ Test JSON generation
- ✓ Test PDF generation (if installed)
- ✓ Check SMTP configuration
- ✓ Check Brevo configuration
- ✓ Show what would be sent

### Manual Testing

```python
# Django shell: python manage.py shell

from threat_intel.models import Report
from threat_intel.services.emailer import send_report_email

# Get a report
report = Report.objects.first()

# Check configuration
from django.conf import settings
print(f"Backend: {settings.THREAT_INTEL_EMAIL_BACKEND}")
print(f"Recipients: {report.recipients}")

# Try sending (without actually sending)
print("Would send to:", report.recipients)

# Actually send
result = send_report_email(report)
print(result)
```

---

## Troubleshooting

### ❌ "No recipients configured"
- **Cause**: Report.recipients is empty
- **Fix**: Add email addresses to report (comma-separated)

### ❌ "BREVO_API_KEY not configured"
- **Cause**: Missing Brevo API key
- **Fix**: Get key from https://www.brevo.com/settings/api/
- **Set**: `BREVO_API_KEY = "xkeysib-..."` or environment variable

### ❌ "sib-api-v3-sdk not installed"
- **Cause**: Missing Brevo SDK
- **Fix**: `pip install sib-api-v3-sdk`

### ❌ "WeasyPrint not installed"
- **Cause**: Missing PDF library
- **Fix**: `pip install weasyprint`
- **Note**: System dependencies may be required (see WeasyPrint docs)

### ❌ "Email not sending via SMTP"
- **Check**: Gmail app password (not regular password)
- **Link**: https://myaccount.google.com/apppasswords
- **Update**: EMAIL_HOST_PASSWORD in settings.py

### ❌ "PDF generation fails"
- **Cause**: Missing system dependencies
- **Linux**: `apt-get install python3-cffi python3-brlapi`
- **Mac**: `brew install python-cffi`
- **Windows**: Install via python-m-cffi

---

## Features Roadmap

### ✅ Implemented
- [x] SMTP email sending (Gmail)
- [x] Brevo API integration
- [x] PDF generation
- [x] Markdown/JSON export
- [x] Web UI modal for sending
- [x] Multiple recipients
- [x] HTML + text email bodies
- [x] Attachment support
- [x] Status tracking (sent_at)

### 🔄 In Progress
- [ ] Email template customization
- [ ] Delivery tracking
- [ ] Webhook integration

### 📅 Planned
- [ ] Batch sending
- [ ] Scheduled reports
- [ ] Email history dashboard
- [ ] Retry logic
- [ ] Dynamic Brevo templates
- [ ] DKIM/SPF config
- [ ] Bounce handling

---

## Support

### Documentation Files
- [`threat_intel/EMAIL_SETUP.md`](threat_intel/EMAIL_SETUP.md) - Complete setup guide
- [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) - What was implemented
- [`.env.example`](.env.example) - Environment variable template

### Test Script
- [`threat_intel/test_email.py`](threat_intel/test_email.py) - Run: `python manage.py shell < threat_intel/test_email.py`

### Code
- [`threat_intel/services/emailer.py`](threat_intel/services/emailer.py) - Core functions
- [`threat_intel/services/report_generator.py`](threat_intel/services/report_generator.py) - Export utilities
- [`threat_intel/views.py`](threat_intel/views.py) - ReportSendView

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: 2026-01-29  
**Backends**: SMTP ✓ + Brevo ✓ (optional)  
**Attachments**: PDF ✓ + Markdown ✓ + JSON ✓
