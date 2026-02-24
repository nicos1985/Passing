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
    ChecklistTemplate,
    ChecklistItem,
    VendorChecklist,
    VendorEvaluation,
    VendorEvaluationItem,
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
    """Agrega clases, marcadores y data-icon para homogeneizar los widgets."""
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


def apply_default_widget_attrs(form_instance):
    """Aplica atributos y estilos predeterminados a todos los campos del formulario."""
    for fname, field in form_instance.fields.items():
        widget = field.widget
        if isinstance(widget, (CheckboxInput, RadioSelect)):
            widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
        else:
            improve_widget_attrs(fname, widget)

class RiskEvaluationForm(forms.ModelForm):
    """Formulario para crear o editar evaluaciones de riesgo ligadas a distintos recursos."""
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
            # If editing an existing Vendor, prefill with the currently assigned template (if any)
            try:
                if getattr(self, 'instance', None) and getattr(self.instance, 'pk', None):
                    assignment = VendorChecklist.objects.filter(vendor=self.instance).first()
                    if assignment and assignment.template_id:
                        self.fields['initial_checklist_template'].initial = assignment.template_id
            except Exception:
                pass
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
    """Formulario para gestionar activos de información con estilizado uniforme."""

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
    """Formulario para crear o editar proveedores y seleccionar una plantilla inicial."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # extra helper field to allow selecting a checklist template at vendor creation
        try:
            from django.urls import reverse
            from django.utils.safestring import mark_safe

            link = reverse('checklist-templates')
            help_html = mark_safe(f'<a href="{link}" target="_blank">Ver plantillas</a>')

            self.fields['initial_checklist_template'] = forms.ModelChoiceField(
                queryset=ChecklistTemplate.objects.filter(active=True),
                required=True,
                label='Plantilla de checklist de requisitos de seguridad',
                help_text=help_html,
            )
        except Exception:
            # safe fallback if model not ready at import
            pass
        # Ensure computed fields are not editable in the form
        self.fields.pop('criticality', None)
        self.fields.pop('control_period', None)
        for fname, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (CheckboxInput, RadioSelect)):
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'
            else:
                improve_widget_attrs(fname, widget)
        # Limit owner choices to users in the current tenant
        try:
            if 'owner' in self.fields:
                self.fields['owner'].queryset = CustomUser.for_current_tenant()
        except Exception:
            # Fallback: leave default queryset if tenant resolution fails
            pass

    
    class Meta:
        model = Vendor
        fields = '__all__'
        exclude = ['created', 'updated']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'finish_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ProjectAssetsForm(ModelForm):
    """Formulario para mantener proyectos y coordinar sus datos temporales."""

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
    """Formulario para administrar clientes con controles básicos de visualización."""

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
    """Formulario que permite definir tratamientos y asociarlos a un recurso específico."""

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
    """Formulario para crear o editar amenazas con descripción ampliada."""

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
    """Formulario para registrar vulnerabilidades y sus descripciones."""

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


class ChecklistTemplateForm(ModelForm):
    """Formulario para definir plantillas de checklist y sus atributos básicos."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_default_widget_attrs(self)

    class Meta:
        model = ChecklistTemplate
        fields = ['name', 'description', 'active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
        }


class ChecklistItemForm(ModelForm):
    """Formulario para editar los ítems que componen una plantilla."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_default_widget_attrs(self)

    class Meta:
        model = ChecklistItem
        fields = ['order', 'text', 'required', 'controls']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'text': forms.Textarea(attrs={'rows': 1}),
        }


class VendorChecklistForm(ModelForm):
    """Formulario para asignar o actualizar checklists de seguridad a proveedores."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_default_widget_attrs(self)

    class Meta:
        model = VendorChecklist
        fields = ['vendor', 'template', 'customized', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


class VendorEvaluationForm(ModelForm):
    """Formulario para registrar evaluaciones programadas a proveedores."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_default_widget_attrs(self)
        try:
            self.fields['performed_by'].queryset = CustomUser.for_current_tenant().filter(is_active=True)
        except Exception:
            self.fields['performed_by'].queryset = CustomUser.objects.filter(is_active=True)

    class Meta:
        model = VendorEvaluation
        fields = ['vendor', 'scheduled_date', 'performed_by', 'performed_at', 'status', 'notes']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'performed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


class VendorEvaluationItemForm(ModelForm):
    """Formulario para capturar las respuestas de cada pregunta en una evaluación."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_default_widget_attrs(self)

    class Meta:
        model = VendorEvaluationItem
        fields = ['question_text', 'result', 'observations']
        widgets = {
            'question_text': forms.HiddenInput(),
            'result': forms.Select(attrs={'class': 'form-select form-control'}),
            'observations': forms.Textarea(attrs={'rows': 1}),
        }


from django.forms import modelformset_factory

VendorEvaluationItemFormSet = modelformset_factory(
    VendorEvaluationItem,
    form=VendorEvaluationItemForm,
    extra=0,
)


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