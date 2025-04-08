from django.db import models
from login.models import CustomUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


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
    name = models.CharField(max_length=255, verbose_name="Nombre")
    status = models.IntegerField(choices=AssetStatus.choices, default=AssetStatus.ACTIVE, verbose_name='Estado')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    personal_data_level = models.IntegerField(choices=PersonalDataLevelChoice.choices, default=PersonalDataLevelChoice.NONE, verbose_name='Nivel de datos personales')
    owner = models.CharField(max_length=255)
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



# Create your models here.
class InformationAssets(RiskEvaluableObject):

    value = models.FloatField(blank=True, null=True, verbose_name='Valor monetario')
    acquisition_date = models.DateField(auto_now=True, verbose_name='Fecha de adquisicion')
    asset_type = models.IntegerField(choices=AssetType, verbose_name='Tipo activo')
    location = models.CharField(max_length=255, blank=True, null=True ,verbose_name="Localizacion")
    serial_number = models.CharField(max_length=200, blank=True, null=True, verbose_name='Nro serie')
    information_classification = models.IntegerField(choices=Info_Class, default=Info_Class.CONFIDENTIAL, verbose_name='Clasificacion de la informacion')
    

    class Meta():
        verbose_name = 'Activo de la informacion'
        verbose_name_plural = 'Activos de la informacion'
        

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

    vendor_type = models.IntegerField(choices=VendorType, default=VendorType.OTHERS, verbose_name='Tipo proveedor')
    value_range = models.IntegerField(choices=ValueRange, default=ValueRange.NO_ONEROUS, verbose_name='Rango valor')
    contract_time = models.IntegerField(choices=ContractTime, default=ContractTime.PERMANENT, verbose_name='Tiempo de contrato')
    access_information = models.IntegerField(choices=Info_Class, default=Info_Class.INTERN, verbose_name='Acceso a la informacion')
    disponibility_impact = models.IntegerField(choices=DisponibilityImpact, default=DisponibilityImpact.MEDIUM, verbose_name='Impacto en disponibilidad')
    criticality = models.IntegerField(choices=Criticality, default=Criticality.NON_CRITICAL, verbose_name='Criticidad')
    control_period = models.IntegerField(choices=ControlPeriod, default=ControlPeriod.MONTH_4, verbose_name='Periodo de control')
    service_standard = models.TextField(blank=True, null=True, verbose_name="Estandar de Servicio")
    start_date = models.DateField(verbose_name='Fecha de inicio')
    finish_date = models.DateField(blank=True, null=True, verbose_name='Fecha de finalizacion')

    class Meta():
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'


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

    proyect_type = models.IntegerField(choices=ProjectType, verbose_name='Tipo de proyecto')
    start_date = models.DateField(verbose_name='Fecha de inicio')
    finish_date = models.DateField(blank=True, null=True, verbose_name='Fecha de finalizacion')
    budget = models.FloatField(blank=True, null=True, verbose_name='Presupuesto')
    associated_users = models.ManyToManyField(CustomUser, related_name='Proyectos')

    class Meta():
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'



class ClientCompany(RiskEvaluableObject):

    
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

class Threat(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nombre")
    type_threat = models.IntegerField(choices=TypeThreat.choices, default=TypeThreat.OTHERS, verbose_name='Tipo de amenaza')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Amenaza'
        verbose_name_plural = 'Amenazas'

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
    name = models.CharField(max_length=255, verbose_name="Nombre")
    type_vulnerability = models.IntegerField(choices=TypeVulnerability.choices, default=TypeThreat.OTHERS, verbose_name='Tipo de vulnerabilidad')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now_add=True)

class LevelOfImpact(models.IntegerChoices):
    INCIDENTAL = 0, 'Incidental'
    MINOR = 1, 'Menor'
    MODERATE = 2, 'Moderado'
    IMPORTANT = 3, 'Importante'
    EXTREME = 4, 'Extremo'

class LevelOfProbability(models.IntegerChoices):
    UNLIKELY = 0, 'Poco probable'
    POSSIBLE = 1, 'Posible'
    MODERATE = 2, 'Moderado'
    LIKELY = 3, 'Probable'
    VERY_LIKELY = 4, 'Muy probable'

class LevelOfRisk(models.IntegerChoices):
    VERY_LOW = 0, 'Muy bajo'
    LOW = 1, 'Bajo'
    MODERATE = 2, 'Moderado'
    HIGH = 3, 'Alto'
    VERY_HIGH = 4, 'Muy alto'



class RiskEvaluation(models.Model):
    evaluated_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    evaluated_id = models.PositiveIntegerField()
    evaluated_object = GenericForeignKey('evaluated_type', 'evaluated_id')
    #Aca los campos de evaluacion de riesgo
    threat = models.ForeignKey('Threat', on_delete=models.CASCADE, verbose_name='Amenaza')
    vulnerability = models.ForeignKey('Vulnerability', on_delete=models.CASCADE, verbose_name='Vulnerabilidad')
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    confidenciality_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en confidencialidad')
    integrity_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en integridad')
    availability_impact = models.IntegerField(choices=LevelOfImpact.choices, default=LevelOfImpact.INCIDENTAL, verbose_name='Impacto en disponibilidad')
    impact_value = models.FloatField(blank=True, null=True, verbose_name='Valor de impacto')
    probability = models.IntegerField(choices=LevelOfProbability.choices, default=LevelOfProbability.INCIDENTAL, verbose_name='Probabilidad')
    risk_value = models.FloatField(blank=True, null=True, verbose_name='Valor de riesgo')
    risk_level = models.IntegerField(choices=LevelOfRisk.choices, default=LevelOfRisk.INCIDENTAL, verbose_name='Nivel de riesgo')
