from django.forms import CheckboxInput, FileInput, ModelForm, PasswordInput, RadioSelect, Select, TextInput, Textarea  
from .models import ClientCompany, InformationAssets, Project, RiskEvaluation, Threat, Vendor, Vulnerability
from django.contrib.contenttypes.models import ContentType
from django import forms

class RiskEvaluationForm(forms.ModelForm):
    model_type = forms.ModelChoiceField(
        queryset=ContentType.objects.filter(model__in=[
            'informationassets', 'vendor', 'project', 'clientcompany'
        ]),
        label="Objeto evaluable"
    )
    
        
    object_id = forms.IntegerField(label="ID del objeto")
    threat = forms.ModelChoiceField(queryset=Threat.objects.all())
    vulnerability = forms.ModelChoiceField(queryset=Vulnerability.objects.all())

    class Meta:
        model = RiskEvaluation
        fields = ['model_type', 'object_id', 'threat', 'vulnerability', 'description', 'confidenciality_impact', 'integrity_impact', 'availability_impact', 'probability']
        widgets = {
            'threat': Select(attrs={'class': 'form-control'}),
            'vulnerability': Select(attrs={'class': 'form-control'}),   
            'description': Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'form-control'}),
            'confidenciality_impact': Select(attrs={'class': 'form-control'}),
            'integrity_impact': Select(attrs={'class': 'form-control'}),
            'availability_impact': Select(attrs={'class': 'form-control'}),
            'probability': Select(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.evaluated_type = self.cleaned_data['model_type']
        instance.evaluated_id = self.cleaned_data['object_id']
        if commit:
            instance.save()
        return instance

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
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'finish_date': forms.DateInput(attrs={'type': 'date'}),
        }


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
