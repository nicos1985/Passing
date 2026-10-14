# threat_intel/forms.py
from django import forms
from django.core.validators import validate_email
from .models import Report, Review, Source, TechTag


class ReportForm(forms.ModelForm):
    """Formulario para crear o editar reportes de inteligencia de amenazas."""
    recipients = forms.CharField(
        label='Destinatarios',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'usuario1@example.com, usuario2@example.com'}),
    )

    def clean_recipients(self):
        addresses = [value.strip() for value in self.cleaned_data['recipients'].split(',')]
        addresses = [value for value in addresses if value]
        if not addresses:
            raise forms.ValidationError('Ingresá al menos un destinatario.')
        for address in addresses:
            validate_email(address)
        return list(dict.fromkeys(addresses))

    class Meta:
        model = Report
        fields = ['subject', 'body_md', 'recipients']
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
        }


class ReportSendForm(forms.Form):
    """Formulario para configurar el envío de reportes por email."""
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
    """Formulario para crear o actualizar revisiones de ítems de inteligencia."""
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
    """Formulario para gestionar fuentes de inteligencia de amenazas."""
    class Meta:
        model = Source
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TechTagForm(forms.ModelForm):
    """Formulario para crear o editar etiquetas tecnológicas."""
    class Meta:
        model = TechTag
        fields = ['name', 'keywords', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'keywords': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Keywords separated by commas'
            }),
        }

    def clean_keywords(self):
        keywords = self.cleaned_data['keywords']
        if not isinstance(keywords, list) or not all(
            isinstance(value, str) and value.strip() for value in keywords
        ):
            raise forms.ValidationError('Ingresá una lista JSON de palabras o frases.')
        return list(dict.fromkeys(value.strip().lower() for value in keywords))
