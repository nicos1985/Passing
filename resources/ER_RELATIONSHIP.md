# Diagrama ER del app `resources`

Este diagrama resume las principales entidades del módulo `resources` y cómo se relacionan para soportar activos, proveedores, checklists, evaluaciones y tratamientos.

## Relaciones clave
- `RiskEvaluableObject` es la base abstracta heredada por activos, proveedores, proyectos y clientes.
- Un `InformationAssets` puede tener múltiples `AssetAction` (préstamos o devoluciones) y cada acción se anota con dos usuarios distintos (`user` y `performed_by`).
- Los proveedores (`Vendor`) gestionan asignaciones de `ChecklistTemplate`, ciclos de `VendorEvaluation` y su respectiva descomposición en `VendorEvaluationItem`.
- Las `VendorEvaluation` referencian una plantilla asignada y generan tratamientos automáticos cuando alguna respuesta no cumple.
- Una `RiskEvaluation` apunta a cualquier recurso evaluable (activo, proveedor, proyecto o cliente) y se apoya en amenazas (`Threat`), vulnerabilidades (`Vulnerability`) y un tratamiento (`Treatment`).

## Diagrama
```mermaid
graph TD
	RiskEvaluableObject -->|hereda| InformationAssets
	RiskEvaluableObject -->|hereda| Vendor
	RiskEvaluableObject -->|hereda| Project
	RiskEvaluableObject -->|hereda| ClientCompany

	InformationAssets -->|acciones| AssetAction
	AssetAction -->|user| CustomUser
	AssetAction -->|performed_by| CustomUser

	Vendor -->|tiene| VendorChecklist
	VendorChecklist -->|plantilla| ChecklistTemplate
	ChecklistTemplate -->|contiene| ChecklistItem
	Vendor -->|tiene| VendorEvaluation
	VendorEvaluation -->|responde| VendorEvaluationItem
	VendorEvaluation -->|performed_by| CustomUser
	VendorEvaluationItem -->|snapshot| ChecklistItem

	RiskEvaluation -->|analiza| Threat
	RiskEvaluation -->|analiza| Vulnerability
	RiskEvaluableObject -->|es evaluado| RiskEvaluation
	RiskEvaluation -->|coordina| Treatment

	ChecklistTemplate -->|respaldada por| VendorEvaluation
```
