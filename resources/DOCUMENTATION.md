# Documentación de la app `resources`

## Visión general

La aplicación `resources` centraliza la trazabilidad de activos, proveedores, evaluaciones de riesgo y tratamientos asociados dentro del tenant. Combina modelos con vistas CRUD, formularios personalizados y lógica administrativa que permite: rastrear préstamos/devoluciones de activos, gestionar listas de chequeo para proveedores, ejecutar evaluaciones de riesgo y disparar tratamientos automáticos cuando corresponde.

---

## Modelos principales

### `RiskEvaluableObject` (abstracto)
- Campos clave: `name`, `status`, `description`, `personal_data_level`, `owner` (`CustomUser`), `created`, `updated`.
- Hereda la relación con usuarios y provee el esquema base para activos (`InformationAssets`), proveedores (`Vendor`), proyectos (`Project`) y clientes (`ClientCompany`).

### `InformationAssets`
- Hereda de `RiskEvaluableObject` y añade campos financieros y técnicos (`value`, `acquisition_date`, `asset_type`, `location`, `serial_number`, `information_classification`).
- Se usa como centro de operaciones de `AssetAction` (préstamos/devoluciones) y aparece en formularios y vistas específicas.

### `Vendor` y sus helpers
- Extiende `RiskEvaluableObject` con campos de riesgo (`vendor_type`, `value_range`, `contract_time`, `control_period`, entre otros).
- Métodos clave:
  - `schedule_next_evaluation()`: programa la siguiente evaluación pendiente según el `control_period` y snapshots del checklist asignado.
  - `compute_criticality()` y `compute_control_period()`: determinan valores iniciales al crear el proveedor.
  - Propiedades: `is_critical_vendor`, `assigned_checklist_template`, `assigned_template_name`.

### Checklists y Evaluaciones de proveedor
- `ChecklistTemplate` y `ChecklistItem` representan plantillas reutilizables; cada `VendorChecklist` asigna una plantilla a un proveedor.
- `VendorEvaluation` guarda el estado (`status`, `scheduled_date`, `performed_by`, `reminder_sent_at`) y replicas automáticas de los items con `VendorEvaluationItem`.
- Métodos destacados de `VendorEvaluation`:
  - `create_items_from_assigned_checklist()`: copia los ítems de la plantilla asignada.
  - `ensure_treatment_for_failures()`: genera un `Treatment` automático si la evaluación completada tiene ítems que no cumplen.
  - Propiedades: `days_until_scheduled`, `can_be_performed`, `assigned_checklist_template`.

### Vistas de riesgo y tratamiento
- `RiskEvaluation`: contiene la relación genérica (`GenericForeignKey`) hacia activos/proveedores/clientes/proyectos.
- En `save()`: calcula `impact_value`, `risk_value`, `risk_level` y crea automáticamente un `Treatment` (si el riesgo es moderado o superior y no existe uno previo).
- `Treatment`: maneja etapas (`TreatmentStage`), hitos (`stage_changed_at`, `stage_changed_by`) y campos de seguimiento (`analysis_notes`, `immediate_actions`, `corrective_actions`). Métodos útiles:
  - `set_stage()`: actualiza etapa, timestamp y usuario.
  - `get_stage_badge()` y `get_deadline_badge()` para badges de UI.

### Actuaciones sobre activos (`AssetAction`)
- `AssetActionType` define `LOAN` y `RETURN`, mientras que `AssetActionStatus` controla `PENDING`, `CONFIRMED`, `REJECTED`.
- Validaciones en `clean()`: evita préstamos dobles o devoluciones sin préstamo activo, incluso cuando se confirma por token.
- Campos como `confirmation_token`, `user`, `performed_by`, `due_date` y métodos auxiliares (`badge_confidenciality`, `treatment_status_link`).

### Otros modelos complementarios
- `Project` y `ClientCompany`: amplían `RiskEvaluableObject` para gestionar proyectos y clientes, con fechas, presupuestos y contactos.
- `Threat` y `Vulnerability`: enumeraciones (`TypeThreat`, `TypeVulnerability`) y campos descriptivos.
- `RiskEvaluation` también conserva relaciones con `Threat`, `Vulnerability` y el `Treatment` asociado.
- Enumeraciones auxiliares: `Controls`, `TypeTreatment`, `TreatmentOportunity`, `ApplicationPeriodicity`, `ControlAutomation`, `Priority`, `ImplementationStatus`, `LevelOfImpact/Probability/Risk`.

---

## Formularios y capturas de datos

### Formularios de riesgo y tratamiento
- `RiskEvaluationForm`: ajusta dinámicamente `object_id` según el `ContentType` seleccionado, da placeholders e iconos consistentes y preselecciona la plantilla asignada al proveedor cuando edita.
- `TreatmentForm`: solicita `model_type` y `object_id`, valida la fecha límite y aplica estilos; excluye campos redundantes y maneja cargas dinámicas de `object_id` en edición.

### Formularios de recursos básicos
- `InformationAssetsForm`, `ProjectAssetsForm`, `ClientAssetsForm`: heredan de `ModelForm`, aplican clases `form-control` y excluyen `created/updated`.
- `VendorForm`: agrega un campo auxiliar `initial_checklist_template`, limita `owner` a usuarios del tenant y oculta campos calculados (`criticality`, `control_period`).
- `VendorChecklistForm`, `ChecklistTemplateForm`, `ChecklistItemForm`: exponen los campos necesarios para asignar plantillas.

### Formularios de acciones
- `LoanForm` y `ReturnForm`: limitan los activos según si están prestados o disponibles, asignan `action_type`, envían notificaciones por email y asignan el usuario actual cuando corresponde.
- `VendorEvaluationForm` y `VendorEvaluationItemFormSet`: permiten crear evaluaciones y procesar resultados con `performed_by` acotado a usuarios del tenant.
- `VendorEvaluationItemForm`: oculta `question_text` y expone `result` y `observations` con select y textarea.

---

## Vistas y rutas clave

### Activos y acciones
- `AssetListView`, `AssetCreateView`, `AssetUpdateView`, `AssetDeleteView`, `AssetDetailView`: CRUD estándar con contexto enriquecido (badges, enlaces relacionados).
- `LoanCreateView` y `ReturnCreateView`: crean solicitudes pendientes y envían emails de confirmación al beneficiario o al poseedor actual.
- `AssetActionListView` / `AssetActionAllListView`: países con historial filtrado por activo o por usuario.
- Funciones de utilidad: `asset_tracking()` muestra asset + titular actual; `confirm_asset_action()` consume el token y valida el estado.
- `GenericResourceDetailView`: vista reutilizable para mostrar campos de cualquier modelo `RiskEvaluableObject`.

### Proveedores, proyectos y clientes
- CRUD completo para `Vendor`, `Project` y `ClientCompany` con vistas `ListView/CreateView/UpdateView/DeleteView/DetailView`.
- `VendorCreateView` también asigna checklist inicial y programa la primera evaluación.

### Evaluaciones y tratamientos
- `get_objects_by_type()` y `crear_evaluacion()`: API AJAX para `object_id` y formulario de riesgo con integración opcional con `threat_intel`.
- `RiskEvaluationDetailView`, `RiskEvaluationListView`, `RiskEvaluationDeleteView`: listan evaluaciones por riesgo, incluyen filtros dinámicos y posibilidad de forzar tratamientos.
- `force_create_treatment()`: crea manualmente un tratamiento aunque el nivel de riesgo sea bajo.
- `TreatmentListView`, `crear_tratamiento()`, `TreatmentUpdateView`, `TreatmentDeleteView`, `advance_treatment_stage()`: gestionan el ciclo de vida del tratamiento y permiten cambiar de etapa con notas.
- `test_colreorder()`: vista simple para testear UI.

### Amenazas, vulnerabilidades y checklists
- CRUD para `Threat` y `Vulnerability` con vistas dedicadas.
- `ChecklistTemplateListView`, `ChecklistTemplateCreateView`, `checklist_template_detail()`, `VendorChecklistCreateView`: permiten crear plantillas, editarlas con inline formsets y asignarlas a proveedores.

### Evaluaciones de proveedores
- `VendorEvaluationCreateView`, `VendorEvaluationDetailView`: permiten ingresar evaluaciones detalladas y completar items (`VendorEvaluationItemFormSet`).
- `VendorEvaluationPendingOwnerListView`: muestra evaluaciones pendientes con contexto generado por `build_pending_evaluations_context()` y `get_pending_evaluations_queryset()`.
- `VendorEvaluationPendingOwnerListView` y `VendorEvaluationAdmin` exponen la lógica necesaria para administradores y propietarios.

---

## Señales

- `treatment_post_save` (`signals.py`): cuando un `Treatment` llega a `IMPLEMENTED`, genera automáticamente una *re-evaluación* (`RiskEvaluation`) para el mismo objeto, marcándola con `skip_treatment=True` para evitar bucles.

---

## Administración (`admin.py`)

- `InformationAssetAdmin`: lista campos relevantes, marca `created/updated` como readonly y permite búsqueda por nombre/usuario.
- `AssetActionAdmin`: incluye `get_asset_name()` para mostrar el activo, filtra por tipo de acción y habilita búsqueda sobre el nombre del activo y usuario.
- `VendorAdmin`: incorpora inline de `VendorChecklist` y `VendorEvaluation`, permitiendo inspeccionar asignaciones y evaluaciones desde el panel.
- `VendorEvaluationAdmin`: añade una ruta personalizada (`pending-evaluations/`) y usa `build_pending_evaluations_context()` para mostrar evaluaciones pendientes desde el admin.
- Registro de `ChecklistTemplate`, `VendorChecklist`, `VendorEvaluation` y `VendorEvaluationItem` con las inlines y filtros adecuados.

---

## URLs (`urls.py`)

- Activos: `asset-list/`, `asset-create/`, `asset-update/<pk>`, `asset-detail/<pk>`, `asset-delete/<pk>`.
- Proveedores y checklists: `vendor-*`, `checklist-templates`, `checklist-template/<pk>/`, `vendor-evaluation-*`, `vendor-checklist-create/`, `vendor-evaluations/pending/`.
- Proyectos y clientes: rutas `project-*` y `client-*` con vistas genéricas.
- Evaluaciones de riesgo: `evaluation-create/`, `evaluation/<pk>/`, `evaluation-list/`, `evaluation-delete/<pk>/`, `evaluation/<pk>/force-treatment/`, `ajax/get-objects/`.
- Tratamientos: `treatment-*`, `treatment-advance/<pk>/`, `test-colreorder/`, `crear-tratamiento/`.
- Amenazas y vulnerabilidades: `threat-*`, `vulnerability-*`.
- Acciones de activos: `asset-loan/`, `asset-return/`, `asset-tracking/`, `asset-actions/`, `asset-actions/user/`, `asset-action-confirm/<uuid:token>/`.

---

## Siguientes pasos sugeridos
1. Mantener este documento actualizado cada vez que se agregue un modelo, formulario o vista importante dentro de `resources`.
2. Repetir el mismo patrón para las demás apps críticas (`accounts`, `login`, `notifications`...) para conservar consistencia.
3. Considerar la generación de diagramas de relaciones para acompañar este mapa textual cuando el equipo lo necesite.
