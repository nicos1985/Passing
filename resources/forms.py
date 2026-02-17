from django.forms import (
    CheckboxInput,
    FileInput,
    ModelForm,
    PasswordInput,
    RadioSelect,
    Select,
    TextInput,
    Textarea,
)
from .models import (
    ClientCompany,
    InformationAssets,
    Project,
    RiskEvaluableObject,
    RiskEvaluation,
    Threat,
    Treatment,
    Vendor,
    Vulnerability,
)
from .models import AssetAction, AssetActionType
from django.contrib.contenttypes.models import ContentType
from django import forms
import logging
from login.models import CustomUser

logger = logging.getLogger(__name__)
from itertools import chain


# Small helper: map common field names to FontAwesome icons and placeholders
ICON_MAP = {
    'model_type': 'fa-cubes',
    'object_id': 'fa-hashtag',
    'threat': 'fa-exclamation-triangle',
    'vulnerability': 'fa-bug',
    'description': 'fa-file-lines',
    'confidenciality_impact': 'fa-chart-bar',
    'integrity_impact': 'fa-chart-bar',
    'availability_impact': 'fa-chart-bar',
    'probability': 'fa-chart-line',
    'start_date': 'fa-calendar',
    'finish_date': 'fa-calendar',
    'deadline': 'fa-calendar',
    'name': 'fa-tag',
    'url': 'fa-link',
    'email': 'fa-envelope',
    'recipients': 'fa-users',
    'ticket_ref': 'fa-ticket-simple',
}

def improve_widget_attrs(field_name, widget):
    """Add consistent classes, placeholders and data-icon for templates."""
    # base control class
    existing = widget.attrs.get('class', '')
    classes = f"{existing} form-control"
    widget.attrs['class'] = classes.strip()
    # autocomplete off by default
    widget.attrs.setdefault('autocomplete', 'off')
    # placeholder from field name (improve in template rendering)
    placeholder = widget.attrs.get('placeholder') or f"Ingrese {field_name.replace('_', ' ')}"
    widget.attrs['placeholder'] = placeholder
    # attach data-icon if known
    icon = ICON_MAP.get(field_name)
    if icon:
        widget.attrs['data-icon'] = icon

class RiskEvaluationForm(forms.ModelForm):
    model_type = forms.ModelChoiceField(
        queryset=ContentType.objects.filter(model__in=[
            'informationassets', 'vendor', 'project', 'clientcompany'
        ]),
        label="Objeto evaluable"
    )
    object_id = forms.ChoiceField(label="ID del objeto")
    threat = forms.ModelChoiceField(queryset=Threat.objects.all())
    vulnerability = forms.ModelChoiceField(queryset=Vulnerability.objects.all())

    class Meta:
        model = RiskEvaluation
        fields = ['model_type', 'object_id', 'threat', 'vulnerability', 'description',
                  'confidenciality_impact', 'integrity_impact', 'availability_impact', 'probability', 'treatment']
        widgets = {
            'description': Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'form-control'}),
            'confidenciality_impact': Select(attrs={'class': 'form-control'}),
            'integrity_impact': Select(attrs={'class': 'form-control'}),
            'availability_impact': Select(attrs={'class': 'form-control'}),
            'probability': Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If POST (data provided) or editing an instance, populate object_id choices
        # so Django's ChoiceField validation accepts the submitted value.
        try:
            # Django forms can receive bound data as the first positional arg
            data = None
            if args:
                data = args[0]
            else:
                data = kwargs.get('data')
            if data:
                model_type_id = data.get('model_type')
                if model_type_id:
                    try:
                        ct = ContentType.objects.get(pk=model_type_id)
                        model_class = ct.model_class()
                        self.fields['object_id'].choices = [(str(obj.pk), str(obj)) for obj in model_class.objects.all()]
                    except Exception:
                        self.fields['object_id'].choices = []

            # If form is bound to an instance (edit), populate choices from that instance's content type
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'pk', None):
                try:
                    ct = self.instance.evaluated_type if hasattr(self.instance, 'evaluated_type') else None
                    if ct is None and getattr(self.instance, 'evaluated_type_id', None):
                        ct = ContentType.objects.get(pk=self.instance.evaluated_type_id)
                    if ct:
                        model_class = ct.model_class()
                        self.fields['object_id'].choices = [(str(obj.pk), str(obj)) for obj in model_class.objects.all()]
                        if getattr(self.instance, 'evaluated_id', None) is not None:
                            self.fields['object_id'].initial = str(self.instance.evaluated_id)
                except Exception:
                    self.fields['object_id'].choices = []
        except Exception:
            # Fall back safely if ContentType lookups fail during import-time form construction
            self.fields['object_id'].choices = []

        # Improve widget attrs consistently (placeholders, icons, classes)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.evaluated_type = self.cleaned_data['model_type']
        # object_id comes from a ChoiceField as string, convert to int
        instance.evaluated_id = int(self.cleaned_data['object_id'])
        if commit:
            instance.save()
        return instance

class InformationAssetsForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)
            
    class Meta:
        model = InformationAssets
        fields = '__all__'
        exclude = ['created', 'updated']


class VendorForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)

    
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
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)
            
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

                logger.info("Edit mode - loaded object_id choices: %s", choices)
                logger.debug("Initial object_id: %s", self.fields['object_id'].initial)

            except Exception as e:
                logger.exception("Error cargando object_id en modo edición")
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
                    logger.exception('Error al cargar object_id choices dinámicamente')
                    self.fields['object_id'].choices = []
        else:
            # En GET inicial, dejarlo vacío
            self.fields['object_id'].choices = []
        

        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(field_name, widget)

    class Meta:
        model = Treatment
        exclude = ['content_type','object_id','created', 'updated']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'},format='%Y-%m-%d'),
            'analysis_notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'immediate_actions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'corrective_actions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'stage': forms.Select(attrs={'class': 'form-select'}),
        }
    

class ThreatForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)
            
    class Meta:
        model = Threat
        fields = '__all__'
        exclude = ['created', 'updated']
        widgets = {
            'description': Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'form-control'}),
        }


class VulnerabilityForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)
            
    class Meta:
        model = Vulnerability
        fields = '__all__'
        exclude = ['created', 'updated']
        widgets = {
            'description': Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'form-control'}),
        }


class LoanForm(forms.ModelForm):
    """Formulario para crear un préstamo (AssetAction with LOAN)."""
    class Meta:
        model = AssetAction
        fields = ['asset', 'user', 'description', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow assets that are not currently loaned
        available_assets = InformationAssets.objects.all()
        # filter out assets that are currently loaned
        available_assets = [a for a in available_assets if not a.is_loaned]
        self.fields['asset'].queryset = InformationAssets.objects.filter(pk__in=[a.pk for a in available_assets])
        # user choices: solo usuarios del tenant actual
        try:
            self.fields['user'].queryset = CustomUser.for_current_tenant().filter(is_active=True)
        except Exception:
            # fallback seguro por si no existe el helper
            self.fields['user'].queryset = CustomUser.objects.filter(is_active=True)

        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)

    def save(self, commit=True, performed_by=None):
        instance = super().save(commit=False)
        instance.action_type = AssetActionType.LOAN
        if performed_by:
            instance.performed_by = performed_by
        if commit:
            instance.save()
        return instance


class ReturnForm(forms.ModelForm):
    """Formulario para registrar una devolución (AssetAction with RETURN)."""
    class Meta:
        model = AssetAction
        fields = ['asset', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow assets that are currently loaned
        loaned = [a for a in InformationAssets.objects.all() if a.is_loaned]
        self.fields['asset'].queryset = InformationAssets.objects.filter(pk__in=[a.pk for a in loaned])

        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)

    def save(self, commit=True, performed_by=None):
        instance = super().save(commit=False)
        instance.action_type = AssetActionType.RETURN
        # set user to the current holder if available
        holder = instance.asset.get_current_holder()
        instance.user = holder
        if performed_by:
            instance.performed_by = performed_by
        if commit:
            instance.save()
        return instance