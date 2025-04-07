from django.forms import CheckboxInput, FileInput, ModelForm, PasswordInput, RadioSelect, Select, TextInput, Textarea  
from .models import ClientCompany, InformationAssets, Project, Vendor
from django import forms

class InformationAssetsForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
            
    class Meta:
        model = InformationAssets
        fields = '__all__'
        exclude = ['created', 'updated']


class VendorForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'

    
    class Meta:
        model = Vendor
        fields = '__all__'
        exclude = ['created', 'updated']


class ProjectAssetsForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
            
    class Meta:
        model = Project
        fields = '__all__'
        exclude = ['created', 'updated']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'finish_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ClientAssetsForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
            
    class Meta:
        model = ClientCompany
        fields = '__all__'
        exclude = ['created', 'updated']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'finish_date': forms.DateInput(attrs={'type': 'date'}),
        }
