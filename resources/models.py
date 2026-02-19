from datetime import date, timedelta
from calendar import monthrange
import logging
from django.db import models
from login.models import CustomUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
import uuid
from django.utils.html import format_html, mark_safe
from django.urls import reverse

logger = logging.getLogger(__name__)

################################# MODELOS DE RECURSOS ###############################
class AssetStatus(models.IntegerChoices):
    ACTIVE = 0, 'Activo'
    INACTIVE = 1, 'Inactivo'
    UNDER_REPAIR = 2, 'En Reparacion'
    BACK_UP = 3, 'Back up'

class PersonalDataLevelChoice(models.IntegerChoices):
    NONE = 0, 'Ninguno'
    HIGH = 1, 'Alto'
    MEDIUM = 2, 'Medio'
    LOW = 3, 'Bajo'

class RiskEvaluableObject(models.Model):
    """Base común para objetos que pueden ser evaluados en el módulo de riesgos."""
    name = models.CharField(max_length=255, verbose_name="Nombre")
    status = models.IntegerField(choices=AssetStatus.choices, default=AssetStatus.ACTIVE, verbose_name='Estado')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    personal_data_level = models.IntegerField(choices=PersonalDataLevelChoice.choices, default=PersonalDataLevelChoice.NONE, verbose_name='Nivel de datos personales')
    owner = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='owned_%(class)s', related_query_name='owned_%(class)s', verbose_name='Propietario')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True




    
class AssetType(models.IntegerChoices):
    PC_OR_NOTEBOOK = 0, 'Pc o Notebook'
    MONITOR = 1, 'Monitor'
    PERIFERICAL = 2, 'Perifericos'
    STORAGE_UNIT = 3, 'Unidad de almacenamiento'
    INTERNAL_COMPONENTS = 4, 'Componentes internos'
    WIRE_AND_CONNECTORS = 5, 'Cables y conectores'
    PRINTER = 6, 'Impresoras'
    SERVER = 7, 'Servidores'
    SWITCH = 8, 'Switch'
    ROUTER = 9, 'Router'
    MODEM = 10, 'Modem'
    DOCUMENT = 11, 'Documento'
    SOFTWARE = 12, 'Software'
    SERVICE = 13, 'Servicio'
    MAIL = 14, 'Email'
    PASSWORD = 15, 'Password'
    KEY = 16, 'Key'
    OTHER = 17, 'Otro'

class Info_Class(models.IntegerChoices):
    PUBLIC = 0, 'Publica'
    INTERN = 1, 'Interna'
    CONFIDENTIAL = 2, 'Confidencial'




class InformationAssets(RiskEvaluableObject):
    """Representa un activo de información y hereda campos comunes de `RiskEvaluableObject`."""

    value = models.FloatField(blank=True, null=True, verbose_name='Valor monetario')
    acquisition_date = models.DateField(auto_now=True, verbose_name='Fecha de adquisicion')
    asset_type = models.IntegerField(choices=AssetType, verbose_name='Tipo activo')
    location = models.CharField(max_length=255, blank=True, null=True ,verbose_name="Localizacion")
    serial_number = models.CharField(max_length=200, blank=True, null=True, verbose_name='Nro serie')
    information_classification = models.IntegerField(choices=Info_Class, default=Info_Class.CONFIDENTIAL, verbose_name='Clasificacion de la informacion')
    

    class Meta():
        verbose_name = 'Activo de la informacion'
        verbose_name_plural = 'Activos de la informacion'

    def __str__(self):
        return self.name

# Controles normalizados (utilizados por checklist y tratamientos)
class Controls(models.IntegerChoices):
    A5_INFORMATION_SECURITY_POLICIES = 0, 'A.5 Políticas de seguridad de la información'
    A6_ORGANIZATION_OF_INFORMATION_SECURITY = 1, 'A.6 Organización de la seguridad de la información'
    A7_HUMAN_RESOURCE_SECURITY = 2, 'A.7 Seguridad en los recursos humanos'
    A8_ASSET_MANAGEMENT = 3, 'A.8 Gestión de activos'
    A9_ACCESS_CONTROL = 4, 'A.9 Control de acceso'
    A10_CRYPTOGRAPHY = 5, 'A.10 Criptografía'
    A11_PHYSICAL_AND_ENVIRONMENTAL_SECURITY = 6, 'A.11 Seguridad física y ambiental'
    A12_OPERATIONS_SECURITY = 7, 'A.12 Seguridad en las operaciones'
    A13_COMMUNICATION_SECURITY = 8, 'A.13 Seguridad en las comunicaciones'
    A14_SYSTEM_ACQUISITION_DEVELOPMENT_AND_MAINTENANCE = 9, 'A.14 Adquisición, desarrollo y mantenimiento de sistemas'
    A15_SUPPLIER_RELATIONSHIPS = 10, 'A.15 Relaciones con los proveedores'
    A16_INFORMATION_SECURITY_INCIDENT_MANAGEMENT = 11, 'A.16 Gestión de incidentes de seguridad de la información'
    A17_INFORMATION_SECURITY_ASPECTS_OF_BUSINESS_CONTINUITY = 12, 'A.17 Aspectos de seguridad de la información en la continuidad del negocio'
    A18_COMPLIANCE = 13, 'A.18 Cumplimiento'


##########################################################################
# MODELOS PARA CHECKLISTS Y EVALUACIONES DE PROVEEDORES
##########################################################################

class ChecklistTemplate(models.Model):
    """Plantilla reutilizable que agrupa preguntas para evaluaciones a proveedores."""
    name = models.CharField(max_length=255, verbose_name='Nombre plantilla')
    description = models.TextField(blank=True, null=True, verbose_name='Descripcion')
    created_by = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.SET_NULL, related_name='created_checklist_templates')
    active = models.BooleanField(default=True, verbose_name='Activa')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plantilla de checklist'
        verbose_name_plural = 'Plantillas de checklist'

    def __str__(self):
        return self.name


class ChecklistItem(models.Model):
    """Pregunta individual perteneciente a una plantilla y ordenada por su posición deseada."""
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name='items', verbose_name='Plantilla')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    text = models.TextField(verbose_name='Pregunta / Punto a evaluar')
    required = models.BooleanField(default=True, verbose_name='Requerido')
    controls = models.IntegerField(choices=Controls.choices, default=Controls.A15_SUPPLIER_RELATIONSHIPS, verbose_name='Control relacionado')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Item de checklist'
        verbose_name_plural = 'Items de checklist'
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} - {self.text[:60]}'


class VendorChecklist(models.Model):
    """Asigna una plantilla a un proveedor; permite marcar si fue personalizada."""
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='checklist_assignments')
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name='vendor_assignments')
    customized = models.BooleanField(default=False, verbose_name='Personalizada')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas de personalizacion')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Checklist asignada a proveedor'
        verbose_name_plural = 'Checklists asignadas a proveedores'
        unique_together = ('vendor', 'template')

    def __str__(self):
        return f'{self.vendor} <- {self.template.name}'


class VendorEvaluationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    IN_PROGRESS = 'IN_PROGRESS', 'En progreso'
    COMPLETED = 'COMPLETED', 'Completada'
    CANCELLED = 'CANCELLED', 'Cancelada'


class EvaluationResult(models.IntegerChoices):
    COMPLIES = 0, 'Cumple'
    DOES_NOT_COMPLY = 1, 'No cumple'
    NOT_APPLICABLE = 2, 'No aplica'


class VendorEvaluation(models.Model):
    """Almacena el ciclo de vida y estado de la evaluación de un proveedor."""
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='evaluations', verbose_name='Proveedor')
    scheduled_date = models.DateField(blank=True, null=True, verbose_name='Fecha programada')
    performed_by = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.SET_NULL, related_name='performed_vendor_evaluations', verbose_name='Evaluado por')
    performed_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de evaluacion')
    status = models.CharField(max_length=20, choices=VendorEvaluationStatus.choices, default=VendorEvaluationStatus.PENDING, verbose_name='Estado')
    notes = models.TextField(blank=True, null=True, verbose_name='Observaciones generales')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)
    reminder_sent_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha aviso enviado')

    class Meta:
        verbose_name = 'Evaluacion de proveedor'
        verbose_name_plural = 'Evaluaciones de proveedores'

    def __str__(self):
        return f'Evaluacion {self.vendor} - {self.scheduled_date or "-"} ({self.get_status_display()})'

    @property
    def days_until_scheduled(self):
        """Calcula cuántos días faltan (o pasaron) para la evaluación."""
        if not self.scheduled_date:
            return None
        today = timezone.localdate()
        return (self.scheduled_date - today).days

    @property
    def days_until_scheduled_abs(self):
        """Devuelve la distancia absoluta entre la fecha programada y hoy."""
        days = self.days_until_scheduled
        if days is None:
            return None
        return abs(days)

    def can_be_performed(self, lead_days=None):
        """Indica si la evaluación puede ejecutarse según el plazo o si ya está vencida."""
        days = self.days_until_scheduled
        if days is None:
            return False
        if days < 0:
            return True
        if lead_days is None:
            return True
        return days <= lead_days

    @property
    def assigned_checklist_template(self):
        """Retorna la plantilla actualmente asignada al proveedor."""
        assignment = self.vendor.checklist_assignments.order_by('-updated').first()
        return assignment.template if assignment else None

    @property
    def assigned_template_name(self):
        """Nombre de la plantilla asignada (si existe)."""
        template = self.assigned_checklist_template
        return template.name if template else None

    def create_items_from_assigned_checklist(self):
        """Clona los ítems de la plantilla asignada para preservar el estado evaluado."""
        # Busca la plantilla asignada al proveedor y copia los items (snapshot) a la evaluación
        assignment = self.vendor.checklist_assignments.first()
        if not assignment:
            return 0
        count = 0
        for item in assignment.template.items.all():
            VendorEvaluationItem.objects.create(
                evaluation=self,
                checklist_item=item,
                question_text=item.text,
                required=item.required,
                controls=item.controls,
            )
            count += 1
        return count

    def ensure_treatment_for_failures(self):
        """Genera un tratamiento automático cuando hay items que no cumplen."""
        if self.status != VendorEvaluationStatus.COMPLETED:
            logger.debug('ensure_treatment_for_failures: evaluation %s status %s (not completed)', self.pk, self.status)
            return
        failing = self.items.filter(result=EvaluationResult.DOES_NOT_COMPLY)
        if not failing.exists():
            logger.debug('ensure_treatment_for_failures: evaluation %s has no failing items', self.pk)
            return
        ct = ContentType.objects.get_for_model(self.vendor)
        existing = Treatment.objects.filter(content_type=ct, object_id=self.vendor.pk, name__icontains=f"Evaluacion {self.pk}").first()
        if existing:
            logger.debug('ensure_treatment_for_failures: treatment already exists for evaluation %s', self.pk)
            return

        failing_items = []
        for it in failing:
            obs = f" (Obs: {it.observations})" if it.observations else ""
            failing_items.append(f"- {it.question_text}{obs}")

        desc_lines = [
            f"Tratamiento generado automaticamente por evaluacion {self.pk} del proveedor {self.vendor}.",
            "",
            "Puntos que no cumplen:",
        ]
        desc_lines.extend(failing_items)
        full_description = "\n".join(desc_lines)

        responsible = self.performed_by or CustomUser.for_current_tenant().first()
        if responsible is None:
            responsible = CustomUser.objects.filter(is_superuser=True).first()

        logger.info('Creating automated treatment for evaluation %s (vendor %s) with %s failing items', self.pk, self.vendor, failing.count())

        Treatment.objects.create(
            name=f'Tratamiento por Evaluacion de proveedor {self.pk}',
            treatment_type=TypeTreatment.REDUCE,
            description=full_description,
            controls=Controls.A15_SUPPLIER_RELATIONSHIPS,
            content_type=ct,
            object_id=self.vendor.pk,
            deadline=timezone.now().date() + timedelta(days=30),
            treatment_responsible=responsible,
            treatment_oportunity=TreatmentOportunity.CORRECTIVE,
            application_periodicity=ApplicationPeriodicity.TEMPORAL,
            control_automation=ControlAutomation.MANUAL,
            priority=Priority.PRIORITY,
        )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            try:
                self.create_items_from_assigned_checklist()
            except Exception:
                pass
        self.ensure_treatment_for_failures()


class VendorEvaluationItem(models.Model):
    """Snapshot de una pregunta del checklist para cada evaluación de proveedor."""
    evaluation = models.ForeignKey(VendorEvaluation, on_delete=models.CASCADE, related_name='items', verbose_name='Evaluacion')
    checklist_item = models.ForeignKey(ChecklistItem, on_delete=models.SET_NULL, blank=True, null=True, related_name='+', verbose_name='Item plantilla')
    question_text = models.TextField(verbose_name='Texto de la pregunta (snapshot)')
    required = models.BooleanField(default=True, verbose_name='Requerido')
    controls = models.IntegerField(choices=Controls.choices, default=Controls.A15_SUPPLIER_RELATIONSHIPS, verbose_name='Control relacionado')
    result = models.IntegerField(choices=EvaluationResult.choices, default=EvaluationResult.COMPLIES, verbose_name='Resultado')
    observations = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Item de evaluacion'
        verbose_name_plural = 'Items de evaluacion'

    def __str__(self):
        return f'{self.evaluation} - {self.question_text[:60]} -> {self.get_result_display()}'

    def get_current_holder(self):
        """Devuelve el usuario que actualmente tiene el activo (si está prestado), o None."""
        try:
            # Only consider confirmed actions when determining current holder
            last_action = self.actions.filter(status='CONFIRMED').order_by('-timestamp').first()
            if last_action and last_action.action_type == AssetActionType.LOAN:
                return last_action.user
        except Exception:
            return None
        return None

    @property
    def is_loaned(self):
        return self.get_current_holder() is not None
        

class VendorType(models.IntegerChoices):
    BANKING_AND_FINANCIAL_SERVICES = 0, 'Banking and Financial Services'
    FUEL = 1, 'Fuel'
    MAIL_SERVICE = 2, 'Mail Service'
    INPUTS = 3, 'Inputs'
    INTERNET = 4, 'Internet'
    INSURANCE = 5, 'Insurance'
    STORAGE_SERVICES = 6, 'Storage Services'
    MAINTENANCE_AND_CLEANING_SERVICES = 7, 'Maintenance and Cleaning Services'
    CLOUD_SERVICES = 8, 'Cloud Services'
    INSTALLATION_SERVICES = 9, 'Installation Services'
    TELEPHONE_SERVICES = 10, 'Telephone Services'
    BUSINESS_SERVICES = 11, 'Business Services'
    ESSENTIAL_SERVICES = 12, 'Essential Services'
    MEDICAL_SERVICES = 13, 'Medical Services'
    PROFESSIONAL_SERVICES = 14, 'Professional Services'
    TECHNICAL_SERVICES = 15, 'Technical Services'
    OTHERS = 16, 'Otros'

class ValueRange(models.IntegerChoices):
    NO_ONEROUS = 0, 'No Oneroso'
    ONEROUS = 1, 'Oneroso'

class ContractTime(models.IntegerChoices):
    PERMANENT = 0, 'Permanente'
    TEMPORAL = 1, 'Temporal'

class DisponibilityImpact(models.IntegerChoices):
    HIGH = 0, 'Alto'
    MEDIUM = 1, 'Medio'
    LOW = 2, 'Bajo'

class Criticality(models.IntegerChoices):
    CRITICAL = 0, 'Critico'
    NON_CRITICAL = 1, 'No Crítico'

class ControlPeriod(models.IntegerChoices):
    MONTH_4 = 0, '4 meses'
    MONTH_6 = 1, '6 meses'
    UNIQUE = 2, 'Unico'


class Vendor(RiskEvaluableObject):
    """Proveedor interno con métricas de riesgo y evaluaciones periódicas."""

    vendor_type = models.IntegerField(choices=VendorType, default=VendorType.OTHERS, verbose_name='Tipo proveedor')
    value_range = models.IntegerField(choices=ValueRange, default=ValueRange.NO_ONEROUS, verbose_name='Rango valor')
    contract_time = models.IntegerField(choices=ContractTime, default=ContractTime.PERMANENT, verbose_name='Tiempo de contrato')
    access_information = models.IntegerField(choices=Info_Class, default=Info_Class.INTERN, verbose_name='Acceso a la informacion')
    disponibility_impact = models.IntegerField(choices=DisponibilityImpact, default=DisponibilityImpact.MEDIUM, verbose_name='Impacto en disponibilidad')
    criticality = models.IntegerField(choices=Criticality, default=Criticality.NON_CRITICAL, verbose_name='Criticidad')
    control_period = models.IntegerField(choices=ControlPeriod, default=ControlPeriod.MONTH_4, verbose_name='Periodo de control')
    # service_standard removed: not used anymore
    start_date = models.DateField(verbose_name='Fecha de inicio')
    finish_date = models.DateField(blank=True, null=True, verbose_name='Fecha de finalizacion')

    class Meta():
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
    

    def __str__(self):
        return self.name

    @staticmethod
    def _add_months(origin, months):
        """Añade meses a una fecha respetando el número de días de cada mes."""
        if origin is None or months is None:
            return None
        month = origin.month - 1 + months
        year = origin.year + month // 12
        month = month % 12 + 1
        day = min(origin.day, monthrange(year, month)[1])
        return origin.replace(year=year, month=month, day=day)

    def evaluation_interval_months(self):
        """Devuelve la periodicidad (en meses) según el `control_period`."""
        mapping = {
            ControlPeriod.MONTH_4: 4,
            ControlPeriod.MONTH_6: 6,
            ControlPeriod.UNIQUE: None,
        }
        return mapping.get(self.control_period)

    def next_evaluation_due_date(self, from_date=None):
        """Calcula la fecha de la siguiente evaluación usando `evaluation_interval_months`."""
        base_date = from_date or self.start_date or date.today()
        months = self.evaluation_interval_months()
        if months is None:
            return None
        return self._add_months(base_date, months)

    def has_pending_evaluation(self):
        """Indica si existen evaluaciones pendientes asociadas al proveedor."""
        return self.evaluations.filter(status=VendorEvaluationStatus.PENDING).exists()

    def schedule_next_evaluation(self, *, from_date=None, force=False):
        """Programa la próxima evaluación, evitando duplicar pendientes a menos que se fuerce."""
        if not force and self.has_pending_evaluation():
            logger.debug('Vendor %s already has pending evaluation, skipping schedule', self)
            return None
        due_date = self.next_evaluation_due_date(from_date)
        if due_date is None:
            logger.debug('Vendor %s control_period %s yields no due date', self, self.control_period)
            return None
        evaluation = VendorEvaluation.objects.create(
            vendor=self,
            scheduled_date=due_date,
            status=VendorEvaluationStatus.PENDING,
        )
        evaluation.create_items_from_assigned_checklist()
        return evaluation

    @property
    def is_critical_vendor(self):
        return self.access_information == Info_Class.CONFIDENTIAL or self.disponibility_impact == DisponibilityImpact.HIGH

    def compute_criticality(self):
        """Calcula la criticidad inicial basada en acceso a información y disponibilidad."""
        return Criticality.CRITICAL if self.is_critical_vendor else Criticality.NON_CRITICAL

    def compute_control_period(self):
        """Determina el período de control recomendado (4 o 6 meses)."""
        return ControlPeriod.MONTH_4 if self.is_critical_vendor else ControlPeriod.MONTH_6


class ProjectType(models.IntegerChoices):
    OPERATIONS = 0, 'Proyectos de Operaciones / Producción'
    TECNOLOGY = 1, 'Proyectos de Tecnología / IT'
    MARKETING = 2, 'Proyectos de Marketing / Comercial'
    HUMAN_RESOURCES = 3, 'Proyectos de Recursos Humanos'
    COPORATE = 4, 'Proyectos Estratégicos / Corporativos'
    FINANCE = 5, 'Proyectos de Finanzas / Administración'
    INNOVATION = 6, 'Proyectos de Innovación / I+D'
    OTHERS = 7, 'Otros'


class Project(RiskEvaluableObject):
    """Proyecto que puede ser evaluado y vinculado a múltiples usuarios responsables."""

    proyect_type = models.IntegerField(choices=ProjectType, verbose_name='Tipo de proyecto')
    start_date = models.DateField(verbose_name='Fecha de inicio')
    finish_date = models.DateField(blank=True, null=True, verbose_name='Fecha de finalizacion')
    budget = models.FloatField(blank=True, null=True, verbose_name='Presupuesto')
    associated_users = models.ManyToManyField(CustomUser, related_name='Proyectos')

    class Meta():
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'
    
    def __str__(self):
        return self.name



class ClientCompany(RiskEvaluableObject):
    """Cliente externo cuyo contrato se evalúa y rastrea en el módulo de riesgos."""

    
    cuit = models.CharField(max_length=255, verbose_name="CUIT")
    address = models.CharField(max_length=255, verbose_name="Direccion")
    phone = models.CharField(max_length=255, verbose_name="Telefono")
    email = models.EmailField(max_length=255, verbose_name="Email")
    service_standard = models.TextField(blank=True, null=True, verbose_name="Estandar de Servicio")
    start_date = models.DateField(verbose_name='Fecha de inicio')
    finish_date = models.DateField(blank=True, null=True, verbose_name='Fecha de finalizacion')


    class Meta():
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.name

############################ EVALUACION DE RIESGO #############################

class TypeThreat(models.IntegerChoices):
    
    PHYSICAL_DAMAGE = 0, 'Dano fisico'
    NATUAL_EVENT = 1, 'Evento natural'
    SERVICES_LOST = 2, 'Perdida de servicios'
    RADIATION = 3, 'Radiacion'
    INFORMATION_COMPROMISED = 4, 'Informacion comprometida'
    UNAUTHORIZED_ACCESS = 5, 'Acceso no autorizado'
    TECNICAL_FAILURE = 6, 'Fallo tecnico'
    FUNCTIONAL_FAILURE = 7, 'Fallo funcional'
    COMERCIAL = 8, 'Comercial'
    PIRATERY = 9, 'Pirateria'
    SOCIAL_ENGINEERING = 10, 'Ingenieria social'
    HUMAN_ERROR = 11, 'Error humano'
    THEFT = 12, 'Robo'
    SPYING = 13, 'Espionaje'
    INTRUSION = 14, 'Intrusion'
    TERRORISM = 15, 'Terrorismo'
    OTHERS = 16, 'Otros'
    THREAT_INTEL = 17, 'Inteligencia de amenazas'
    

class Threat(models.Model):
    """Catalogo de amenazas que alimentan las evaluaciones de riesgo."""
    name = models.CharField(max_length=255, verbose_name="Nombre")
    type_threat = models.IntegerField(choices=TypeThreat.choices, default=TypeThreat.OTHERS, verbose_name='Tipo de amenaza')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Amenaza'
        verbose_name_plural = 'Amenazas'
    
    def __str__(self):
        return self.name

class TypeVulnerability(models.IntegerChoices):
    HARDWARE = 0, 'Hardware'
    SOFTWARE = 1, 'Software'
    RED = 2, 'Red'
    PERSONAL = 3, 'Personal'
    PLACE = 4, 'Lugar'
    ORGANIZACION = 5, 'Organizacion'
    PROCESS = 6, 'Procesos'
    COMERCIAL = 7, 'Comercial'
    OTHERS = 8, 'Otros'

class Vulnerability(models.Model):
    """Catalogo de vulnerabilidades detectables sobre los recursos."""
    name = models.CharField(max_length=255, verbose_name="Nombre")
    type_vulnerability = models.IntegerField(choices=TypeVulnerability.choices, default=TypeThreat.OTHERS, verbose_name='Tipo de vulnerabilidad')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vulnerabilidad'
        verbose_name_plural = 'Vulnerabilidades'

    def __str__(self):
        return self.name

class LevelOfImpact(models.IntegerChoices):
    INCIDENTAL = 1, 'Incidental'
    MINOR = 2, 'Menor'
    MODERATE = 3, 'Moderado'
    IMPORTANT = 4, 'Importante'
    EXTREME = 5, 'Extremo'

class LevelOfProbability(models.IntegerChoices):
    UNLIKELY = 1, 'Poco probable'
    POSSIBLE = 2, 'Posible'
    MODERATE = 3, 'Moderado'
    LIKELY = 4, 'Probable'
    VERY_LIKELY = 5, 'Muy probable'

class LevelOfRisk(models.IntegerChoices):
    VERY_LOW = 0, 'Muy bajo'
    LOW = 1, 'Bajo'
    MODERATE = 2, 'Moderado'
    HIGH = 3, 'Alto'
    VERY_HIGH = 4, 'Muy alto'



class RiskEvaluation(models.Model):
    """Evaluación de riesgo asociada a un activo, proveedor, proyecto o cliente."""
    
    evaluated_id = models.PositiveIntegerField()
    evaluated_object = GenericForeignKey('evaluated_type', 'evaluated_id')
    evaluated_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    #Aca los campos de evaluacion de riesgo
    threat = models.ForeignKey('Threat', on_delete=models.CASCADE, verbose_name='Amenaza')
    vulnerability = models.ForeignKey('Vulnerability', on_delete=models.CASCADE, verbose_name='Vulnerabilidad')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    confidenciality_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en confidencialidad')
    integrity_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en integridad')
    availability_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en disponibilidad')
    impact_value = models.FloatField(blank=True, null=True, verbose_name='Valor de impacto')
    probability = models.IntegerField(choices=LevelOfProbability.choices, default=LevelOfProbability.UNLIKELY, verbose_name='Probabilidad')
    risk_value = models.FloatField(blank=True, null=True, verbose_name='Valor de riesgo')
    risk_level = models.IntegerField(blank=True, null=True, choices=LevelOfRisk.choices, default=LevelOfRisk.VERY_LOW, verbose_name='Nivel de riesgo')
    treatment = models.OneToOneField('Treatment', on_delete=models.CASCADE, blank=True, null=True, verbose_name='Tratamiento asociado', related_name='risk_evaluation',)
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evaluacion de riesgo'
        verbose_name_plural = 'Evaluaciones de riesgo'
    
    def __str__(self):
        return f'{self.evaluated_object} - {self.threat}'
    
    def save(self, *args, **kwargs):
        """Calcula métricas de riesgo y genera tratamientos automáticos según el nivel."""
        # Calcular impact_value si no está seteado
        self.impact_value = (
            self.confidenciality_impact +
            self.integrity_impact +
            self.availability_impact
        ) / 3

        # Calcular risk_value
        self.risk_value = self.impact_value * self.probability

        # Evaluar nivel de riesgo según thresholds
        if self.risk_value <= 4:
            self.risk_level = LevelOfRisk.VERY_LOW
        elif self.risk_value <= 9:
            self.risk_level = LevelOfRisk.LOW
        elif self.risk_value <= 14:
            self.risk_level = LevelOfRisk.MODERATE
        elif self.risk_value <= 19:
            self.risk_level = LevelOfRisk.HIGH
        else:
            self.risk_level = LevelOfRisk.VERY_HIGH

        is_new = self.pk is None  # <=== importante
        super().save(*args, **kwargs)

        # Si no tiene tratamiento, crearlo solo para riesgo moderado o superior
        if (
            not self.treatment
            and not getattr(self, 'skip_treatment', False)
            and self.risk_level is not None
            and self.risk_level >= LevelOfRisk.MODERATE
        ):
            # Determinar tipo de tratamiento según nivel de riesgo (por ahora siempre REDUCE)
            treatment_type = TypeTreatment.REDUCE

            # Crear tratamiento
            treatment = Treatment.objects.create(
                name=f"Tratamiento para evaluación {self.pk}",
                treatment_type=treatment_type,
                description=None,
                controls=Controls.A5_INFORMATION_SECURITY_POLICIES,
                content_type=self.evaluated_type,
                object_id=self.evaluated_id,
                deadline=timezone.now().date() + timedelta(days=30),
                treatment_responsible=CustomUser.for_current_tenant().first(),
                treatment_oportunity=TreatmentOportunity.PREVENTIVE,
                application_periodicity=ApplicationPeriodicity.PERMANENT,
                control_automation=ControlAutomation.MANUAL,
                priority=Priority.NO_PRIORITY,
            )

            # Asociar y volver a guardar la evaluación con su tratamiento
            self.treatment = treatment
            super().save(update_fields=["treatment"])
    
    def get_risk_level_badge(self):
        """Renderiza un badge HTML que muestra gráficamente el nivel de riesgo."""
        level = self.risk_level
        label = self.get_risk_level_display()

        # Posiciones para la aguja
        positions = {
            0: '0%',    # Muy Bajo
            1: '25%',   # Bajo
            2: '50%',   # Moderado
            3: '75%',   # Alto
            4: '100%',  # Muy Alto
        }
        left_pos = positions.get(level, '0%')

        # Colores del texto según nivel
        text_colors = {
            0: '#198754',  # Verde Bootstrap
            1: '#198754',  # Verde
            2: '#ffc107',  # Amarillo
            3: '#fd7e14',  # Naranja
            4: '#dc3545',  # Rojo
        }
        text_color = text_colors.get(level, '#6c757d')  # Gris si no matchea

        html = f"""
        <div style="display:inline-block; text-align:center; font-size:0.85rem; line-height:1.2;">
            <div style="position:relative; width:110px; height:10px;
                        background: linear-gradient(to right, #198754, #ffc107, #fd7e14, #dc3545);
                        border-radius:6px; margin-bottom:4px;">
                <div style="position:absolute; top:-6px; left: calc({left_pos} - 5px);
                            width:0; height:0; border-left:5px solid transparent;
                            border-right:5px solid transparent; border-bottom:6px solid #212529;">
                </div>
            </div>
            <div style="font-weight:500; color:{text_color};">{label}</div>
        </div>
        """


############################# Asset Actions (Prestamo / Devolucion) #############################
from django.core.exceptions import ValidationError

class AssetActionType(models.IntegerChoices):
    LOAN = 0, 'Prestamo'
    RETURN = 1, 'Devolucion'


class AssetAction(models.Model):
    """Registra préstamos y devoluciones asociando el activo, solicitante y estado."""
    asset = models.ForeignKey(InformationAssets, on_delete=models.CASCADE, related_name='actions', verbose_name='Activo')
    action_type = models.IntegerField(choices=AssetActionType.choices, verbose_name='Tipo de accion')
    class AssetActionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        CONFIRMED = 'CONFIRMED', 'Confirmado'
        REJECTED = 'REJECTED', 'Rechazado'

    status = models.CharField(max_length=20, choices=AssetActionStatus.choices, default=AssetActionStatus.PENDING, verbose_name='Estado')
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, null=True, blank=True, verbose_name='Token de confirmacion')
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_actions', verbose_name='Usuario')
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_asset_actions', verbose_name='Accionado por')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')
    description = models.TextField(blank=True, null=True, verbose_name='Motivo / descripcion')
    due_date = models.DateField(blank=True, null=True, verbose_name='Fecha estimada de devolucion')

    class Meta:
        verbose_name = 'Accion de activo'
        verbose_name_plural = 'Acciones de activos'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.asset} -> {self.user or 'N/A'} @ {self.timestamp}"

    def clean(self):
        """Valida reglas de negocio al guardar: evita préstamos dobles y devoluciones inválidas."""
        if not getattr(self, 'asset_id', None):
            raise ValidationError({'asset': 'Debe seleccionar un activo.'})

        # Determine current holder by looking at latest action excluding this instance (if editing)
        # Only consider confirmed actions when deciding current state
        qs = AssetAction.objects.filter(asset_id=self.asset_id, status='CONFIRMED').exclude(pk=self.pk).order_by('-timestamp')
        last = qs.first()

        if self.action_type == AssetActionType.LOAN:
            if last and last.action_type == AssetActionType.LOAN:
                raise ValidationError('El activo ya está prestado. Debe devolverlo antes de prestarlo nuevamente.')

        if self.action_type == AssetActionType.RETURN:
            if not last or last.action_type != AssetActionType.LOAN:
                raise ValidationError('No existe un préstamo activo para devolver este activo.')

    def save(self, *args, **kwargs):
        """Ejecuta validaciones y guarda la acción, asegurando consistencia del flujo."""
        self.full_clean()
        super().save(*args, **kwargs)


    

    def get_impact_badge(self, field_name):
        """Construye un badge HTML que representa visualmente el impacto de un campo."""
        value = getattr(self, field_name)
        label = dict(LevelOfImpact.choices).get(value, 'Desconocido')

        # Mapping color_class o inline style
        if value == 4:  # Importante (naranja)
            style = 'background-color: #fd7e14; color: white;'
            return f'<span class="badge" style="{style}">{label}</span>'
        
        color_class = {
            1: 'bg-success',   # Incidental
            2: 'bg-primary',   # Menor
            3: 'bg-warning',   # Moderado
            5: 'bg-danger',    # Extremo
        }.get(value, 'bg-secondary')

        return f'<span class="badge {color_class} text-white">{label}</span>'
    
    def badge_confidenciality(self):
        """Badge específico para confidencialidad."""
        return self.get_impact_badge('confidenciality_impact')

    def badge_integrity(self):
        """Badge específico para integridad."""
        return self.get_impact_badge('integrity_impact')

    def badge_availability(self):
        """Badge específico para disponibilidad."""
        return self.get_impact_badge('availability_impact')
    

    def treatment_status_link(self):
        """Entrega un link al estado del tratamiento asociado para mostrarlo en la UI."""
        if not self.treatment_id:
            return format_html('<span class="text-muted">Sin tratamiento</span>')

        badge_html = mark_safe(self.treatment.get_stage_badge())  # Evita que se escape
        url = reverse('treatment-detail', args=[self.treatment.pk])

        return format_html('<a href="{}">{}</a>', url, badge_html)
    

 ###################### TRATAMIENTO DE RIESGO ###########################  
 

class TypeTreatment(models.IntegerChoices):
    """Define los modos de tratamiento de riesgo disponibles."""
    REDUCE = 0, 'Reducir'
    ASUME = 1, 'Asumir'
    TRANSFER = 2, 'Transferir'
    AVOID = 3, 'Evitar'
    NOT_APPLICABLE = 4, 'No aplica'
    
class TreatmentOportunity(models.IntegerChoices):
    """Describe la oportunidad en la que se aplica el tratamiento."""
    PREVENTIVE = 0, 'Preventivo'
    DETECTIVE = 1, 'Detectivo'
    CORRECTIVE = 2, 'Correctivo'

class ApplicationPeriodicity(models.IntegerChoices):
    """Clasifica la periodicidad de aplicación del tratamiento."""
    PERMANENT = 0, 'Permanente'
    TEMPORAL = 1, 'Temporal'
    OCASIONAL = 2, 'Ocasional'

class ControlAutomation(models.IntegerChoices):
    """Indica si el control es manual, automático o semi-automático."""
    MANUAL = 0, 'Manual'
    AUTOMATIC = 1, 'Automatico'
    SEMIAUTOMATIC = 2, 'Semi-automatico'

class Priority(models.IntegerChoices):
    """Prioriza los tratamientos según urgencia o impacto."""
    URGENT = 0, 'Urgente'
    PRIORITY = 1, 'Prioritario'
    NO_PRIORITY = 2, 'No prioritario'

class ImplementationStatus(models.IntegerChoices):
    """Estados heredados para compatibilidad con tablas previas."""
    PENDING = 0, 'Pendiente'
    IN_PROGRESS = 1, 'En progreso'
    COMPLETED = 2, 'Completado'


class TreatmentStage(models.IntegerChoices):
    """Etapas definidas para el ciclo de vida de un tratamiento."""
    PENDING = 0, 'Pendiente'
    ANALYSIS = 1, 'Análisis'
    IN_PROGRESS = 2, 'En proceso'
    IMPLEMENTED = 3, 'Implementado'

class Treatment(models.Model):
    """Registro principal que agrupa datos de implementación de mitigaciones."""
    name = models.CharField(max_length=255, verbose_name="Nombre")
    treatment_type = models.IntegerField(choices=TypeTreatment.choices, default=TypeTreatment.REDUCE, verbose_name='Tipo de tratamiento')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    controls = models.IntegerField(choices=Controls.choices, default=Controls.A5_INFORMATION_SECURITY_POLICIES, verbose_name='Controles Normalizados')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    deadline = models.DateField(verbose_name='Fecha de cumplimiento')
    treatment_responsible = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Responsable de tratamiento')
    treatment_oportunity = models.IntegerField(choices=TreatmentOportunity.choices, default=TreatmentOportunity.PREVENTIVE, verbose_name='Oportunidad de tratamiento')
    application_periodicity = models.IntegerField(choices=ApplicationPeriodicity.choices, default=ApplicationPeriodicity.PERMANENT, verbose_name='Periodicidad de aplicacion')
    control_automation = models.IntegerField(choices=ControlAutomation.choices, default=ControlAutomation.MANUAL, verbose_name='Automatizacion de control')
    priority = models.IntegerField(choices=Priority.choices, default=Priority.NO_PRIORITY, verbose_name='Prioridad')
    # Compatibility column: some DBs/migrations still expect `implementation_status`.
    # Keep this field mapped to the legacy DB column so ORM writes a safe default during creates.
    implementation_status = models.IntegerField(choices=ImplementationStatus.choices, default=ImplementationStatus.PENDING, verbose_name='Estado de implementacion', db_column='implementation_status')
    # New lifecycle stage and activity fields
    stage = models.IntegerField(choices=TreatmentStage.choices, default=TreatmentStage.PENDING, verbose_name='Etapa')
    analysis_notes = models.TextField(blank=True, null=True, verbose_name='Notas de análisis')
    immediate_actions = models.TextField(blank=True, null=True, verbose_name='Acciones inmediatas')
    corrective_actions = models.TextField(blank=True, null=True, verbose_name='Acciones correctivas')
    stage_changed_at = models.DateTimeField(blank=True, null=True, editable=False, verbose_name='Fecha cambio de etapa')
    stage_changed_by = models.ForeignKey(CustomUser, blank=True, null=True, on_delete=models.SET_NULL, related_name='treatment_stage_changes', editable=False, verbose_name='Usuario que cambió etapa')
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tratamiento'
        verbose_name_plural = 'Tratamientos'
    
    def __str__(self):
        return self.name
    
    # legacy `get_status_badge` removed; use `get_stage_badge` which reflects lifecycle stages

    def get_stage_badge(self):
        """Genera un badge HTML para representar visualmente la etapa actual."""
        value = self.stage
        label = dict(TreatmentStage.choices).get(value, 'Desconocido')

        # Map lifecycle stages to badge colors:
        # PENDING -> red, ANALYSIS -> yellow, IN_PROGRESS -> blue, IMPLEMENTED -> green
        color_class = {
            TreatmentStage.PENDING: 'bg-danger',
            TreatmentStage.ANALYSIS: 'bg-warning',
            TreatmentStage.IN_PROGRESS: 'bg-primary',
            TreatmentStage.IMPLEMENTED: 'bg-success',
        }.get(value, 'bg-secondary')

        return f'<span class="badge {color_class} text-white">{label}</span>'

    def set_stage(self, new_stage, user=None):
        """Actualiza la etapa del tratamiento y registra quién y cuándo lo hizo."""
        if new_stage == self.stage:
            return
        self.stage = new_stage
        self.stage_changed_at = timezone.now()
        if user and isinstance(user, CustomUser):
            self.stage_changed_by = user
        self.save(update_fields=['stage', 'stage_changed_at', 'stage_changed_by'])
    
    def get_deadline_badge(self):
        """Badge que colorea el deadline según si está vencido, hoy o pendiente."""
        
        if self.deadline > timezone.now().date():
            return f'<span class="badge bg-danger text-white">{self.deadline}</span>'
        elif self.deadline == timezone.now().date():
            return f'<span class="badge bg-warning text-white">{self.deadline}</span>'
        else:
            return f'<span class="badge bg-success text-white">{self.deadline}</span>'