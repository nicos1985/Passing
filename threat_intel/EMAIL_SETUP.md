# Email Service Configuration Guide

This guide explains how to use the email service for Threat Intelligence reports with SMTP or Brevo.

## Features

✅ **SMTP Backend** (Default - Gmail/Any SMTP server)
- Send reports via Django's EmailBackend
- Supports attachments (PDF, images, etc.)
- Configured in `passing/settings.py`

✅ **Brevo Backend** (SendinBlue API)
- Send reports via Brevo's transactional email API
- Base64 encoded attachment support
- Higher deliverability rates
- Optional batch sending

---

## 1. SMTP Setup (Current)

### Already Configured
Your Django settings use Gmail SMTP:

```python
# passing/settings.py (use environment variables; do NOT store secrets in repo)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "noreply@anima.bot")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")  # set via env/.env in deploy
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@anima.bot")
```

### Sending a Report with SMTP

```python
from threat_intel.services.emailer import send_report_email
from threat_intel.services.report_generator import generate_report_pdf

report = Report.objects.get(id=1)

# Option 1: Send without attachment
result = send_report_email(report)
# Result: {"status": "success", "message": "Email sent via SMTP..."}

# Option 2: Send with PDF attachment
filename, pdf_content = generate_report_pdf(report)
attachments = [(filename, pdf_content, "application/pdf")]
result = send_report_email(report, attachments=attachments)
```

---

## 2. Brevo Setup

### Prerequisites

1. **Install Brevo SDK**:
```bash
pip install sib-api-v3-sdk
```

2. **Get API Key from Brevo**:
   - Go to https://www.brevo.com/
   - Create account or login
   - Navigate to Settings → API → Create API Key
   - Copy your API key (e.g., `xkeysib-1a2b3c4d5e6f7g8h...`)

3. **Add to Django Settings**:

    **Option A: Environment Variable (Recommended)**
    ```bash
    # .env or export command
    export BREVO_API_KEY="xkeysib-REDACTED"
    ```

    **Option B: Settings File**
    ```python
    # passing/settings.py
    BREVO_API_KEY = "xkeysib-REDACTED"
    ```

4. **Configure Backend**:
   ```python
   # passing/settings.py
   THREAT_INTEL_EMAIL_BACKEND = "brevo"  # or set via env: THREAT_INTEL_EMAIL_BACKEND
   ```

### Sending a Report with Brevo

```python
from threat_intel.services.emailer import send_report_email
from threat_intel.services.report_generator import generate_report_pdf

report = Report.objects.get(id=1)

# Option 1: Send via Brevo (configured in settings)
result = send_report_email(report)
# Result: {"status": "success", "message": "Email sent via Brevo...", "data": {...}}

# Option 2: Force Brevo even if SMTP configured
attachments = [(filename, pdf_content, "application/pdf")]
result = send_report_email(report, attachments=attachments, use_brevo=True)

# Check result
if result['status'] == 'success':
    print(f"Email sent! Message ID: {result['data']['message_id']}")
else:
    print(f"Error: {result['message']}")
```

---

## 3. Generate Report Attachments

### PDF Report
```python
from threat_intel.services.report_generator import generate_report_pdf

report = Report.objects.get(id=1)
filename, pdf_bytes = generate_report_pdf(report)
# filename: "threat_report_1_20260129_143022.pdf"
# pdf_bytes: <binary PDF content>
```

Requires: `pip install weasyprint`

### Markdown Report
```python
from threat_intel.services.report_generator import generate_report_markdown

filename, md_bytes = generate_report_markdown(report)
# filename: "threat_report_1_20260129_143022.md"
```

### JSON Report
```python
from threat_intel.services.report_generator import generate_report_json

filename, json_bytes = generate_report_json(report)
# filename: "threat_report_1_20260129_143022.json"
```

---

## 4. Web UI - Send Report with Email

Navigate to report detail page and use the "Enviar Email" button:

```html
<!-- threat_intel_report_detail.html -->
<form method="post" action="{% url 'threat_intel:report-send' report.pk %}">
  {% csrf_token %}
  
  <!-- Send Email Checkbox -->
  <input type="checkbox" name="send_email" value="on"> Enviar por email
  
  <!-- Include PDF Checkbox -->
  <input type="checkbox" name="include_pdf" value="on"> Incluir PDF adjunto
  
  <!-- Use Brevo Checkbox (only if configured) -->
  <input type="checkbox" name="use_brevo" value="on"> Usar Brevo
  
  <button type="submit" class="btn btn-success">Enviar</button>
</form>
```

---

## 5. API Endpoint Example

```python
# threat_intel/views.py - ReportSendView

class ReportSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        
        send_email = request.POST.get('send_email') == 'on'
        include_pdf = request.POST.get('include_pdf') == 'on'
        use_brevo = request.POST.get('use_brevo') == 'on'
        
        attachments = []
        if include_pdf:
            filename, pdf_content = generate_report_pdf(report)
            attachments.append((filename, pdf_content, "application/pdf"))
        
        if send_email:
            result = send_report_email(report, attachments=attachments, use_brevo=use_brevo)
            if result['status'] == 'success':
                report.sent_at = timezone.now()
                report.save()
        
        return redirect('threat_intel:report-detail', pk=pk)
```

---

## 6. Switching Between SMTP and Brevo

### Option 1: Environment Variable
```bash
# Use SMTP (default)
export THREAT_INTEL_EMAIL_BACKEND="smtp"

# Use Brevo
export THREAT_INTEL_EMAIL_BACKEND="brevo"
export BREVO_API_KEY="xkeysib-..."
```

### Option 2: Force in Code
```python
# Always use SMTP
send_report_email(report, use_brevo=False)

# Always use Brevo
send_report_email(report, use_brevo=True)
```

---

## 7. Testing Email Sending

### Test SMTP
```python
from django.core.mail import send_mail

send_mail(
    subject='Test Email',
    message='This is a test',
    from_email='noreply@anima.bot',
    recipient_list=['test@example.com'],
)
```

### Test Brevo
```python
from threat_intel.services.emailer import send_report_email_brevo
from threat_intel.models import Report

report = Report.objects.first()
report.recipients = ['test@example.com']
report.save()

result = send_report_email_brevo(report)
print(result)
```

### Test PDF Generation
```python
from threat_intel.services.report_generator import generate_report_pdf

report = Report.objects.first()
filename, pdf_bytes = generate_report_pdf(report)
print(f"Generated: {filename} ({len(pdf_bytes)} bytes)")
```

---

## 8. Troubleshooting

### ❌ "BREVO_API_KEY not configured"
- Check environment variable: `echo $BREVO_API_KEY`
- Or add to settings.py: `BREVO_API_KEY = "xkeysib-..."`

### ❌ "sib-api-v3-sdk not installed"
- Install: `pip install sib-api-v3-sdk`

### ❌ "WeasyPrint not installed"
- Install: `pip install weasyprint`

### ❌ Email not sending on SMTP
- Check settings in `passing/config.py`
- Verify Gmail app password: https://myaccount.google.com/apppasswords
- Check Django logs for SMTP errors

### ❌ Brevo API errors
- Verify API key is valid at: https://www.brevo.com/settings/api/
- Check sender email is verified in Brevo
- Check recipient email format

---

## 9. Next Steps

- [ ] Add email template customization per tenant
- [ ] Implement batch sending for multiple reports
- [ ] Add email delivery tracking/webhooks
- [ ] Create admin dashboard for email logs
- [ ] Add retry logic for failed sends

---

## File Structure

```
threat_intel/
├── services/
│   ├── emailer.py              # send_report_email() - Main function
│   ├── report_generator.py     # PDF, Markdown, JSON export
│   └── ai.py                   # AI analysis
├── views.py                    # ReportSendView
├── models.py                   # Report model
└── urls.py                     # URL routing
```

---

**Version**: 1.0  
**Last Updated**: 2026-01-29  
**Email Backends**: SMTP (default), Brevo (optional)
