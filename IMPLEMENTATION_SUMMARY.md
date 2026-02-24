# 📧 Email Service Implementation Summary

## What Was Implemented

### 1. **Enhanced Email Service** (`threat_intel/services/emailer.py`)

✅ **Three functions:**
- `send_report_email_smtp()` - Send via Django SMTP (Gmail)
- `send_report_email_brevo()` - Send via Brevo API (SendinBlue)
- `send_report_email()` - Wrapper that chooses based on settings

✅ **Features:**
- ✓ Support for binary attachments (PDF, images, etc.)
- ✓ Base64 encoding for Brevo
- ✓ HTML + Markdown email bodies
- ✓ Multiple recipients support
- ✓ Error handling with detailed messages
- ✓ Flexible backend selection (SMTP or Brevo)

### 2. **Report Generation Utilities** (`threat_intel/services/report_generator.py`)

✅ **Three export formats:**
- `generate_report_pdf()` - HTML to PDF (requires WeasyPrint)
- `generate_report_markdown()` - Export as .md file
- `generate_report_json()` - Export as JSON

### 3. **Enhanced ReportSendView** (`threat_intel/views.py`)

✅ **New functionality:**
- PDF generation with automatic filename
- Email sending with attachments
- Brevo/SMTP backend selection
- Success/error messaging
- Status tracking (sent_at timestamp)

### 4. **Web UI Modal** (`templates/threat_intel_report_detail.html`)

✅ **New modal dialog:**
- Checkbox: "Send by email"
- Checkbox: "Include PDF attachment"
- Radio buttons: Choose SMTP or Brevo backend
- Shows recipients preview
- Help text for missing dependencies
- Smart disable logic (PDF requires email enabled)

### 5. **Forms** (`threat_intel/forms.py`)

✅ **New forms:**
- `ReportForm` - For creating/editing reports
- `ReportSendForm` - For email sending options
- `ReviewForm`, `SourceForm`, `TechTagForm` - Supporting forms

### 6. **Settings Configuration** (`passing/settings.py`)

✅ **Added:**
```python
THREAT_INTEL_EMAIL_BACKEND = "smtp"  # or "brevo"
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
DEFAULT_FROM_NAME = "Threat Intel System"
```

### 7. **Documentation** (`threat_intel/EMAIL_SETUP.md`)

✅ **Complete guide:**
- SMTP setup (already working with Gmail)
- Brevo setup (step-by-step)
- Usage examples
- API integration examples
- Troubleshooting guide
- File structure

### 8. **Test Script** (`threat_intel/test_email.py`)

✅ **For testing:**
- Generate all formats (MD, JSON, PDF)
- Check Brevo configuration
- Simulate email sending
- Run from: `python manage.py shell < threat_intel/test_email.py`

---

## File Changes Summary

```
✓ threat_intel/services/emailer.py          [Modified] +180 lines (attachments + Brevo)
✓ threat_intel/services/report_generator.py [Created]  +120 lines (PDF/MD/JSON export)
✓ threat_intel/views.py                     [Modified] +30 lines (imports + ReportSendView)
✓ threat_intel/forms.py                     [Created]  +100 lines (forms for reports)
✓ templates/threat_intel_report_detail.html [Modified] +100 lines (send modal)
✓ passing/settings.py                       [Modified] +10 lines (email config)
✓ threat_intel/EMAIL_SETUP.md               [Created]  +400 lines (documentation)
✓ threat_intel/test_email.py                [Created]  +150 lines (test script)
```

---

## How to Use

### Option 1: SMTP (Current - Gmail)
Already configured! Just use:

```python
from threat_intel.services.emailer import send_report_email

report = Report.objects.get(id=1)
result = send_report_email(report)
# Sends via Gmail
```

### Option 2: Brevo (Optional Setup)

**Step 1:** Install SDK
```bash
pip install sib-api-v3-sdk
```

**Step 2:** Add API key to environment or settings
```bash
export BREVO_API_KEY="xkeysib-your-key-here"
```

**Step 3:** Use it
```python
result = send_report_email(report, use_brevo=True)
# or set THREAT_INTEL_EMAIL_BACKEND = "brevo" in settings
```

### Option 3: With Attachments
```python
from threat_intel.services.report_generator import generate_report_pdf

# Generate PDF
filename, pdf_bytes = generate_report_pdf(report)
attachments = [(filename, pdf_bytes, "application/pdf")]

# Send with PDF
result = send_report_email(report, attachments=attachments)
```

### Option 4: Web UI
Navigate to report detail page → Click "Enviar por Email" → Configure options → Send

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   ReportSendView                         │
│              (threat_intel/views.py)                     │
│  - Handles POST from web UI                             │
│  - Generates attachments                                 │
│  - Calls send_report_email()                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              send_report_email()                         │
│         (threat_intel/services/emailer.py)              │
│  - Router function (SMTP or Brevo)                      │
│  - Error handling                                        │
│  - Response formatting                                   │
└─────────────────────────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
    ┌─────────────────────┐  ┌──────────────────────┐
    │ send_report_email_  │  │ send_report_email_   │
    │ smtp()              │  │ brevo()              │
    │                     │  │                      │
    │ Django SMTP         │  │ Brevo API v3         │
    │ EmailMultiAlternative
    │ (Gmail)             │  │ SibApiV3Client       │
    └─────────────────────┘  └──────────────────────┘
            │                        │
            ▼                        ▼
    ┌─────────────────────┐  ┌──────────────────────┐
    │ Django Email Backend│  │ Brevo Transactional  │
    │ SMTP (Gmail)        │  │ Email API            │
    └─────────────────────┘  └──────────────────────┘
```

---

## Response Format

Both backends return the same format:

```python
# Success
{
    "status": "success",
    "message": "Email sent via SMTP to 3 recipients",
    "data": {...}  # (Brevo only)
}

# Error
{
    "status": "error",
    "message": "No recipients configured for threat intel email."
}
```

---

## Current Limitations & Next Steps

### Current:
✅ SMTP with Gmail is working
✅ Attachment support (PDF generation requires WeasyPrint)
✅ Brevo API integration ready (requires SDK + API key)
✅ Web UI for easy sending
✅ Multiple email formats

### TODO:
- [ ] Email template customization per tenant
- [ ] Batch sending for multiple reports
- [ ] Delivery tracking (webhooks)
- [ ] Retry logic for failed sends
- [ ] Email history/logging database
- [ ] Admin dashboard for email status
- [ ] Scheduled report sending
- [ ] Brevo dynamic templates support

---

## Quick Start Checklist

For **SMTP (Gmail)**:
- [x] Already configured
- [x] Ready to use

For **Brevo (Optional)**:
- [ ] Install: `pip install sib-api-v3-sdk`
- [ ] Get API key from brevo.com
- [ ] Add BREVO_API_KEY to settings or environment
- [ ] Test with: `python manage.py shell < threat_intel/test_email.py`

For **PDF Support**:
- [ ] Install: `pip install weasyprint`
- [ ] Test with: `python manage.py shell < threat_intel/test_email.py`

---

## Files Modified/Created

| File | Action | Purpose |
|------|--------|---------|
| `threat_intel/services/emailer.py` | Modified | Email sending with attachments |
| `threat_intel/services/report_generator.py` | Created | PDF/MD/JSON export |
| `threat_intel/views.py` | Modified | Enhanced ReportSendView |
| `threat_intel/forms.py` | Created | Forms for reports & sending |
| `templates/threat_intel_report_detail.html` | Modified | Email send modal |
| `passing/settings.py` | Modified | Email backend config |
| `threat_intel/EMAIL_SETUP.md` | Created | Complete documentation |
| `threat_intel/test_email.py` | Created | Testing script |

---

## Testing

Run the test script to verify everything works:

```bash
python manage.py shell < threat_intel/test_email.py
```

This will:
1. ✓ Load a sample report
2. ✓ Generate Markdown export
3. ✓ Generate JSON export
4. ✓ Attempt PDF generation
5. ✓ Check SMTP configuration
6. ✓ Check Brevo configuration
7. ✓ Show what attachments would be sent

---

**Status**: ✅ Ready for use  
**Version**: 1.0  
**Last Updated**: 2026-01-29  
**Backends**: SMTP (Gmail) ✓ + Brevo (optional) ✓
