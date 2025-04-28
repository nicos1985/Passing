from django.forms import CheckboxInput, FileInput, ModelForm, PasswordInput, RadioSelect, Select, TextInput, Textarea  
from .models import ClientCompany, InformationAssets, Project, RiskEvaluableObject, RiskEvaluation, Threat, Treatment, Vendor, Vulnerability
from django.contrib.contenttypes.models import ContentType
from django import forms
from itertools import chain

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


class TreatmentForm(ModelForm):

    model_type = forms.ModelChoiceField(
        queryset=ContentType.objects.filter(model__in=[
            'informationassets', 'vendor', 'project', 'clientcompany'
        ]),
        label="Tipo de Recurso",
        required=True
    )
    
        
    object_id = forms.ChoiceField(label="Recurso")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['deadline'].input_formats = ['%Y-%m-%d']

        #bloque para cargar el objeto en modo edición
        # Si la instancia ya existe, cargar el tipo de modelo y el objeto_id
        if self.instance and self.instance.pk:
            self.fields['model_type'].initial = self.instance.content_type

            try:
                model_class = self.instance.content_type.model_class()
                queryset = model_class.objects.all()
                choices = [(str(obj.pk), str(obj)) for obj in queryset]
                self.fields['object_id'].choices = choices
                self.fields['object_id'].initial = str(self.instance.object_id)
                self.fields['object_id'].widget.attrs['data-selected'] = str(self.instance.object_id)

                print(f"✅ Edit mode - loaded object_id choices: {choices}")
                print(f"🧲 Initial object_id: {self.fields['object_id'].initial}")

            except Exception as e:
                print(f"⚠️ Error cargando object_id en modo edición: {e}")
                self.fields['object_id'].choices = []

        # Cargar dinámicamente choices en POST para que Django valide correctamente
        if 'data' in kwargs:
            data = kwargs['data']
            model_type_id = data.get('model_type')
            if model_type_id:
                try:
                    ct = ContentType.objects.get(pk=model_type_id)
                    model_class = ct.model_class()
                    self.fields['object_id'].choices = [
                        (str(obj.pk), str(obj)) for obj in model_class.objects.all()
                    ]
                except Exception as e:
                    print(f'Error al cargar object_id choices dinámicamente: {e}')
                    self.fields['object_id'].choices = []
        else:
            # En GET inicial, dejarlo vacío
            self.fields['object_id'].choices = []
        

        for field_name, field in self.fields.items():
            if isinstance(field.widget, (CheckboxInput, RadioSelect)):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['autocomplete'] = 'off'

    class Meta:
        model = Treatment
        exclude = ['content_type','object_id','created', 'updated']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'},format='%Y-%m-%d'),
        }
    

