from django import forms

from .models import IntegrationCredential


class IntegrationCredentialForm(forms.ModelForm):
    secret_plain = forms.CharField(
        label="JSON Service Account",
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "Pegá aquí el JSON completo"}),
        required=False,
        help_text="Se cifra con la clave Fernet configurada (CRYPTOGRAPHY_KEY).",
    )

    class Meta:
        model = IntegrationCredential
        fields = ["name", "key_id", "status", "secret_plain"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Credencial Drive"}),
            "key_id": forms.TextInput(attrs={"placeholder": "Opcional"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get("secret_plain"):
            self.add_error("secret_plain", "Debes cargar el JSON de la Service Account.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.service = IntegrationCredential.Service.GOOGLE_DRIVE
        raw_secret = self.cleaned_data.get("secret_plain")
        if raw_secret:
            obj.set_secret(raw_secret)
        if commit:
            obj.save()
            self.save_m2m()
        return obj
