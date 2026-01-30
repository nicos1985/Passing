# threat_intel/forms.py
from django import forms
from .models import Report, Review, Source, TechTag


class ReportForm(forms.ModelForm):
    """Form for creating/updating threat intelligence reports."""
    class Meta:
        model = Report
        fields = ['subject', 'body_md', 'body_html', 'recipients']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Report subject/title'
            }),
            'body_md': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Report content in Markdown format'
            }),
            'body_html': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Report content in HTML format (optional)'
            }),
            'recipients': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Email addresses separated by commas (e.g., user1@example.com, user2@example.com)'
            }),
        }


class ReportSendForm(forms.Form):
    """Form for sending reports via email."""
    BACKEND_CHOICES = [
        ('smtp', 'SMTP (Gmail/Default)'),
        ('brevo', 'Brevo (SendinBlue)'),
    ]
    
    send_email = forms.BooleanField(
        label='Enviar por email',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_pdf = forms.BooleanField(
        label='Incluir PDF como adjunto',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    use_brevo = forms.BooleanField(
        label='Usar Brevo (en lugar de SMTP)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    backend = forms.ChoiceField(
        label='Email Backend',
        choices=BACKEND_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='smtp'
    )


class ReviewForm(forms.ModelForm):
    """Form for creating/updating reviews of threat intel items."""
    class Meta:
        model = Review
        fields = ['decision', 'notes', 'ticket_ref']
        widgets = {
            'decision': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional analysis notes'
            }),
            'ticket_ref': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reference ticket/issue ID (optional)'
            }),
        }


class SourceForm(forms.ModelForm):
    """Form for creating/updating threat intelligence sources."""
    class Meta:
        model = Source
        fields = ['name', 'url', 'api_key', 'enabled']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control'}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TechTagForm(forms.ModelForm):
    """Form for creating/updating technology tags."""
    class Meta:
        model = TechTag
        fields = ['name', 'category', 'keywords']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'keywords': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Keywords separated by commas'
            }),
        }
