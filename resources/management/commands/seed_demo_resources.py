from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from accounts.models import CustomUser
from resources.models import (
    AssetStatus,
    AssetType,
    ClientCompany,
    ContractTime,
    ControlPeriod,
    Criticality,
    DisponibilityImpact,
    Info_Class,
    InformationAssets,
    PersonalDataLevelChoice,
    Project,
    ProjectType,
    ValueRange,
    Vendor,
    VendorType,
)


class Command(BaseCommand):
    help = "Crea o actualiza activos, proveedores, clientes y proyectos de demostracion."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            required=True,
            help="Schema del tenant que recibira los datos (por ejemplo: empresa1).",
        )
        parser.add_argument(
            "--owner",
            default="",
            help="Username o email del propietario. Si se omite, usa un usuario activo del tenant.",
        )

    def handle(self, *args, **options):
        schema_name = options["tenant"].strip()
        owner_identifier = options["owner"].strip()
        Tenant = get_tenant_model()

        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
        except Tenant.DoesNotExist as exc:
            available = ", ".join(
                Tenant.objects.exclude(schema_name="public")
                .order_by("schema_name")
                .values_list("schema_name", flat=True)
            )
            suffix = f" Tenants disponibles: {available}." if available else ""
            raise CommandError(f"No existe el tenant '{schema_name}'.{suffix}") from exc

        with schema_context(schema_name):
            owner = self._find_owner(tenant, owner_identifier)
            if owner is None:
                raise CommandError(
                    f"El tenant '{schema_name}' no tiene usuarios activos para asignar como propietario."
                )

            with transaction.atomic():
                counts = {
                    "activos": self._seed_assets(owner),
                    "proveedores": self._seed_vendors(owner),
                    "clientes": self._seed_clients(owner),
                    "proyectos": self._seed_projects(owner, tenant),
                }

        self.stdout.write(
            self.style.SUCCESS(
                f"Datos demo listos en '{schema_name}' (owner: {owner.username})."
            )
        )
        for label, result in counts.items():
            self.stdout.write(
                f"- {label.capitalize()}: {result['created']} creados, "
                f"{result['updated']} actualizados"
            )

    def _find_owner(self, tenant, identifier):
        users = CustomUser.for_client(tenant).filter(is_active=True)
        if identifier:
            owner = users.filter(username=identifier).first()
            if owner is None:
                owner = users.filter(email__iexact=identifier).first()
            if owner is None:
                raise CommandError(
                    f"No existe un usuario activo '{identifier}' en el tenant '{tenant.schema_name}'."
                )
            return owner
        return users.order_by("-is_superuser", "-is_staff", "pk").first()

    @staticmethod
    def _upsert(model, rows):
        created = 0
        updated = 0
        objects = []
        for row in rows:
            name = row["name"]
            defaults = {key: value for key, value in row.items() if key != "name"}
            obj, was_created = model.objects.update_or_create(
                name=name,
                defaults=defaults,
            )
            objects.append(obj)
            if was_created:
                created += 1
            else:
                updated += 1
        return {"created": created, "updated": updated, "objects": objects}

    def _seed_assets(self, owner):
        return self._upsert(
            InformationAssets,
            [
                {
                    "name": "[DEMO] Notebook Direccion",
                    "description": "Notebook corporativa utilizada por la direccion general.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "value": 1800000,
                    "asset_type": AssetType.PC_OR_NOTEBOOK,
                    "location": "Oficina central - Direccion",
                    "serial_number": "DEMO-NB-001",
                    "information_classification": Info_Class.CONFIDENTIAL,
                },
                {
                    "name": "[DEMO] Servidor de aplicaciones",
                    "description": "Servidor principal de aplicaciones internas.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "value": 8500000,
                    "asset_type": AssetType.SERVER,
                    "location": "Datacenter principal",
                    "serial_number": "DEMO-SRV-001",
                    "information_classification": Info_Class.CONFIDENTIAL,
                },
                {
                    "name": "[DEMO] Plataforma CRM",
                    "description": "Servicio utilizado para administrar clientes y oportunidades.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "value": 2400000,
                    "asset_type": AssetType.SOFTWARE,
                    "location": "Cloud",
                    "serial_number": "DEMO-SW-CRM",
                    "information_classification": Info_Class.CONFIDENTIAL,
                },
                {
                    "name": "[DEMO] Repositorio de backups",
                    "description": "Copias de seguridad cifradas de los sistemas criticos.",
                    "owner": owner,
                    "status": AssetStatus.BACK_UP,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "value": 950000,
                    "asset_type": AssetType.STORAGE_UNIT,
                    "location": "Cloud - Region secundaria",
                    "serial_number": "DEMO-BKP-001",
                    "information_classification": Info_Class.CONFIDENTIAL,
                },
                {
                    "name": "[DEMO] Manual de continuidad",
                    "description": "Procedimientos para recuperar los servicios esenciales.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.NONE,
                    "value": 150000,
                    "asset_type": AssetType.DOCUMENT,
                    "location": "Repositorio documental",
                    "serial_number": "DEMO-DOC-001",
                    "information_classification": Info_Class.INTERN,
                },
            ],
        )

    def _seed_vendors(self, owner):
        today = timezone.localdate()
        return self._upsert(
            Vendor,
            [
                {
                    "name": "[DEMO] Nube Andina",
                    "description": "Proveedor de infraestructura y almacenamiento cloud.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "vendor_type": VendorType.CLOUD_SERVICES,
                    "value_range": ValueRange.ONEROUS,
                    "contract_time": ContractTime.PERMANENT,
                    "access_information": Info_Class.CONFIDENTIAL,
                    "disponibility_impact": DisponibilityImpact.HIGH,
                    "criticality": Criticality.CRITICAL,
                    "control_period": ControlPeriod.MONTH_4,
                    "start_date": today - timedelta(days=420),
                    "finish_date": None,
                },
                {
                    "name": "[DEMO] Conectividad Federal",
                    "description": "Servicio de internet y enlace redundante.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.NONE,
                    "vendor_type": VendorType.INTERNET,
                    "value_range": ValueRange.ONEROUS,
                    "contract_time": ContractTime.PERMANENT,
                    "access_information": Info_Class.INTERN,
                    "disponibility_impact": DisponibilityImpact.HIGH,
                    "criticality": Criticality.CRITICAL,
                    "control_period": ControlPeriod.MONTH_4,
                    "start_date": today - timedelta(days=300),
                    "finish_date": None,
                },
                {
                    "name": "[DEMO] Estudio Legal del Plata",
                    "description": "Asesoria legal y contractual.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.MEDIUM,
                    "vendor_type": VendorType.PROFESSIONAL_SERVICES,
                    "value_range": ValueRange.ONEROUS,
                    "contract_time": ContractTime.PERMANENT,
                    "access_information": Info_Class.INTERN,
                    "disponibility_impact": DisponibilityImpact.LOW,
                    "criticality": Criticality.NON_CRITICAL,
                    "control_period": ControlPeriod.MONTH_6,
                    "start_date": today - timedelta(days=180),
                    "finish_date": None,
                },
                {
                    "name": "[DEMO] Soporte Tecnico Sur",
                    "description": "Mantenimiento preventivo de equipos y redes.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.LOW,
                    "vendor_type": VendorType.TECHNICAL_SERVICES,
                    "value_range": ValueRange.ONEROUS,
                    "contract_time": ContractTime.TEMPORAL,
                    "access_information": Info_Class.INTERN,
                    "disponibility_impact": DisponibilityImpact.MEDIUM,
                    "criticality": Criticality.NON_CRITICAL,
                    "control_period": ControlPeriod.MONTH_6,
                    "start_date": today - timedelta(days=90),
                    "finish_date": today + timedelta(days=275),
                },
            ],
        )

    def _seed_clients(self, owner):
        today = timezone.localdate()
        return self._upsert(
            ClientCompany,
            [
                {
                    "name": "[DEMO] Industrias Horizonte SA",
                    "description": "Cliente industrial con operacion nacional.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.MEDIUM,
                    "cuit": "30-70000001-1",
                    "address": "Av. Industrial 1450, Buenos Aires",
                    "phone": "+54 11 5555-1001",
                    "email": "contacto@horizonte.demo",
                    "service_standard": "SLA 99,5%; soporte en horario comercial.",
                    "start_date": today - timedelta(days=540),
                    "finish_date": None,
                },
                {
                    "name": "[DEMO] Salud Integral SRL",
                    "description": "Red de centros medicos privados.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "cuit": "30-70000002-2",
                    "address": "Calle Salud 820, Rosario",
                    "phone": "+54 341 555-2002",
                    "email": "sistemas@saludintegral.demo",
                    "service_standard": "Atencion prioritaria y respuesta a incidentes en 2 horas.",
                    "start_date": today - timedelta(days=360),
                    "finish_date": None,
                },
                {
                    "name": "[DEMO] Comercio Rio de la Plata",
                    "description": "Empresa de comercio electronico regional.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "cuit": "30-70000003-3",
                    "address": "Av. del Puerto 310, CABA",
                    "phone": "+54 11 5555-3003",
                    "email": "operaciones@riodelaplata.demo",
                    "service_standard": "Disponibilidad mensual objetivo de 99,9%.",
                    "start_date": today - timedelta(days=210),
                    "finish_date": today + timedelta(days=520),
                },
            ],
        )

    def _seed_projects(self, owner, tenant):
        today = timezone.localdate()
        result = self._upsert(
            Project,
            [
                {
                    "name": "[DEMO] Implementacion ISO 27001",
                    "description": "Adecuacion del sistema de gestion de seguridad de la informacion.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.MEDIUM,
                    "proyect_type": ProjectType.COPORATE,
                    "start_date": today - timedelta(days=60),
                    "finish_date": today + timedelta(days=305),
                    "budget": 12000000,
                },
                {
                    "name": "[DEMO] Migracion a infraestructura cloud",
                    "description": "Migracion gradual de aplicaciones y bases de datos.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "proyect_type": ProjectType.TECNOLOGY,
                    "start_date": today - timedelta(days=30),
                    "finish_date": today + timedelta(days=180),
                    "budget": 18500000,
                },
                {
                    "name": "[DEMO] Portal de clientes",
                    "description": "Nuevo portal de autogestion para clientes externos.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.HIGH,
                    "proyect_type": ProjectType.INNOVATION,
                    "start_date": today,
                    "finish_date": today + timedelta(days=150),
                    "budget": 9800000,
                },
                {
                    "name": "[DEMO] Campana comercial regional",
                    "description": "Expansion de la propuesta comercial en nuevas provincias.",
                    "owner": owner,
                    "status": AssetStatus.ACTIVE,
                    "personal_data_level": PersonalDataLevelChoice.LOW,
                    "proyect_type": ProjectType.MARKETING,
                    "start_date": today - timedelta(days=15),
                    "finish_date": today + timedelta(days=120),
                    "budget": 4200000,
                },
            ],
        )
        associated_users = list(CustomUser.for_client(tenant).filter(is_active=True)[:5])
        if not associated_users:
            associated_users = [owner]
        for project in result["objects"]:
            project.associated_users.set(associated_users)
        return result
