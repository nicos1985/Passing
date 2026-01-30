# threat_intel/services/emailer.py
"""
Email service for threat intelligence reports.
Supports SMTP (Django default) and Brevo (SendinBlue) backends.
"""
from __future__ import annotations
from typing import Optional, List, Tuple
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from threat_intel.models import Report


def send_report_email_smtp(
    report: Report,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None
) -> None:
    """
    Send report via SMTP (Django EmailBackend).
    
    Args:
        report: Report instance with subject, body_md, body_html, recipients
        attachments: List of tuples (filename, content, mimetype)
                    e.g., [("report.pdf", pdf_bytes, "application/pdf")]
    
    Raises:
        RuntimeError: If no recipients are configured
    """
    recipients = report.recipients or []
    if not recipients:
        raise RuntimeError("No recipients configured for threat intel email.")

    msg = EmailMultiAlternatives(
        subject=report.subject,
        body=report.body_md,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=recipients,
    )
    
    # Attach HTML alternative
    if report.body_html:
        msg.attach_alternative(report.body_html, "text/html")
    
    # Attach files (PDF, images, etc.)
    if attachments:
        for filename, content, mimetype in attachments:
            msg.attach(filename, content, mimetype)
    
    msg.send()


def send_report_email_brevo(
    report: Report,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None
) -> dict:
    """
    Send report via Brevo (SendinBlue) API.
    Requires 'sib-api-v3-sdk' package and BREVO_API_KEY in settings.
    
    Args:
        report: Report instance
        attachments: List of tuples (filename, content, mimetype)
    
    Returns:
        Response dict from Brevo API
    
    Raises:
        ImportError: If sib_api_v3_sdk not installed
        RuntimeError: If BREVO_API_KEY not configured or no recipients
    """
    try:
        from sib_api_v3_sdk import ApiClient, Configuration
        from sib_api_v3_sdk.apis.transactional_emails_api import TransactionalEmailsApi
        from sib_api_v3_sdk.models.send_smtp_email import SendSmtpEmail
        from sib_api_v3_sdk.models.send_smtp_email_attachment import SendSmtpEmailAttachment
    except ImportError:
        raise ImportError(
            "Brevo SDK not installed. Install with: pip install sib-api-v3-sdk"
        )
    
    # Get API key from settings
    api_key = getattr(settings, "BREVO_API_KEY", None)
    if not api_key:
        raise RuntimeError(
            "BREVO_API_KEY not configured in settings. "
            "Add it to your Django settings or environment variables."
        )
    
    recipients = report.recipients or []
    if not recipients:
        raise RuntimeError("No recipients configured for threat intel email.")
    
    # Configure API
    config = Configuration()
    config.api_key["api-key"] = api_key
    
    api_client = ApiClient(config)
    api_instance = TransactionalEmailsApi(api_client)
    
    # Prepare recipients list
    to_list = [{"email": email.strip()} for email in recipients]
    
    # Prepare email object
    email_data = SendSmtpEmail(
        subject=report.subject,
        html_content=report.body_html or f"<p>{report.body_md}</p>",
        sender={
            "name": getattr(settings, "DEFAULT_FROM_NAME", "Threat Intel"),
            "email": getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        },
        to=to_list,
    )
    
    # Attach files if provided
    if attachments:
        email_data.attachment = []
        for filename, content, mimetype in attachments:
            # Brevo requires base64 encoding
            import base64
            b64_content = base64.b64encode(content).decode('utf-8')
            
            attachment = SendSmtpEmailAttachment(
                name=filename,
                content=b64_content,
                type=mimetype
            )
            email_data.attachment.append(attachment)
    
    # Send email
    try:
        response = api_instance.send_transac_email(email_data)
        return {
            "status": "success",
            "message_id": getattr(response, "message_id", None),
            "response": response
        }
    except Exception as e:
        raise RuntimeError(f"Brevo API error: {str(e)}")


def send_report_email(
    report: Report,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None,
    use_brevo: bool = False
) -> dict:
    """
    Send report email using configured backend (SMTP or Brevo).
    
    Args:
        report: Report instance
        attachments: List of tuples (filename, content, mimetype)
        use_brevo: Force Brevo backend (default: False uses SMTP)
    
    Returns:
        Response dict: {"status": "success"/"error", "message": str}
    
    Example:
        # Simple text + PDF attachment
        pdf_bytes = b"...PDF content..."
        attachments = [("report.pdf", pdf_bytes, "application/pdf")]
        send_report_email(report, attachments=attachments)
        
        # Force Brevo
        send_report_email(report, attachments=attachments, use_brevo=True)
    """
    backend = getattr(settings, "THREAT_INTEL_EMAIL_BACKEND", "smtp").lower()
    
    if use_brevo or backend == "brevo":
        try:
            result = send_report_email_brevo(report, attachments)
            return {
                "status": "success",
                "message": f"Email sent via Brevo to {len(report.recipients or [])} recipients",
                "data": result
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    else:
        # Default: SMTP
        try:
            send_report_email_smtp(report, attachments)
            return {
                "status": "success",
                "message": f"Email sent via SMTP to {len(report.recipients or [])} recipients"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
