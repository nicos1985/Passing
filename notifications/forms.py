"""Formularios para generar notificaciones de contraseñas compartidas."""

from django import forms
from login.models import CustomUser
from notifications.models import AdminNotification

class CreateNotificationForm(forms.ModelForm):
    """Recoge el usuario destinatario y el comentario para la solicitud."""
    id_user_share = forms.ModelChoiceField(
        queryset=CustomUser.for_current_tenant().filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label = 'Usuario a compartir',
        empty_label="Seleccione un usuario"  # Etiqueta personalizada
    )
    class Meta:
        model = AdminNotification
        fields = ['id_user_share', 'comment']
        labels = {
            'comment': 'Comentario',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control','style':'height:100px;'}),
        }
    





