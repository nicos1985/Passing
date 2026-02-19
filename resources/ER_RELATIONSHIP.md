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
%%{init: { 'theme': 'base', 'themeVariables': { 'primaryColor': '#0b5fff', 'edgeLabelBackground':'#ffffff', 'fontSize':'14px' }}}%%
erDiagram
    RiskEvaluableObject <|-- InformationAssets : hereda
    RiskEvaluableObject <|-- Vendor : hereda
    RiskEvaluableObject <|-- Project : hereda
    RiskEvaluableObject <|-- ClientCompany : hereda

    InformationAssets ||--o{ AssetAction : "acciones"
    AssetAction }o--|| CustomUser : "user"
    AssetAction }o--|| CustomUser : "performed_by"

    Vendor ||--|{ VendorChecklist : "tiene"
    VendorChecklist }o--|| ChecklistTemplate : "plantilla"
    ChecklistTemplate ||--|{ ChecklistItem : "contiene"
    Vendor ||--|{ VendorEvaluation : "tiene"
    VendorEvaluation ||--|{ VendorEvaluationItem : "responde"
    VendorEvaluation }o--|| CustomUser : "performed_by"
    VendorEvaluationItem }o--|| ChecklistItem : "snapshot"

    RiskEvaluation }o--|| Threat : "analiza"
    RiskEvaluation }o--|| Vulnerability : "analiza"
    RiskEvaluableObject ||--o{ RiskEvaluation : "es evaluado"
    RiskEvaluation ||--|| Treatment : "coordina"

    ChecklistTemplate ||--o{ VendorEvaluation : "respaldada por"
```
