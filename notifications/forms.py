from django import forms

from notifications.models import AdminNotification

class CreateNotificationForm(forms.ModelForm):

    class Meta:
        model = AdminNotification
        fields = ['id_user_share', 'comment']
        
    





