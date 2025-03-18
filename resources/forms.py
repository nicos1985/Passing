from django.forms import CheckboxInput, FileInput, ModelForm, PasswordInput, RadioSelect, Select, TextInput, Textarea  
from .models import InformationAssets, Location
from django import forms

class InformationAssetsUpdateForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
            
    class Meta:
        model = InformationAssets
        fields = '__all__'
        exclude = ['created', 'updated']
        
    

class InformationAssetsCreateForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'

    class Meta:
        model = InformationAssets
        fields = '__all__'
        exclude = ['created', 'updated']
        