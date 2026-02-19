# Documentación del app `threat_intel`

Este módulo centraliza el pipeline de inteligencia de amenazas: ingestión de fuentes externas, normalización de ítems (CVE/advisories), análisis asistido por IA, generación de reportes y registro de decisiones internas.

## Arquitectura general
- **Ingesta:** cada `Source` tiene un `SourceState` que guarda el cursor y último run. `RawItem` conserva el payload original, mientras `IntelItem` representa la versión normalizada. Los `TechTag` permiten marcar tecnologías relevantes al stack.
- **Pipeline:** las `Run` registran ciclos de monitoreo. Cada `RunItem` enlaza con los `IntelItem` extraídos. `AIAnalysis` genera recomendaciones automatizadas y `Review` documenta las decisiones humanas.
- **Producción:** `Report` agrupa resultados de una corrida y puede exportarse/enviarse por email usando `services.report_generator` y `services.emailer`.

## Modelos clave
1. `TechTag`: catálogo de tecnologías (Ubuntu, AWS, Kubernetes) con keywords para matching.
2. `Source`: fuentes externas (NVD, CISA, MSRC) que alimentan los `RawItem`. Cada fuente dispone de un `SourceState` con el cursor y fecha del último run exitoso.
3. `RawItem`: item crudo por fuente con payload JSON. Se normaliza en `IntelItem` manteniendo trazabilidad.
4. `IntelItem`: representación enriquecida (CVE, advisory, severidad, tech tags, referencias) que alimenta análisis y decisiones. Se relaciona con `AIAnalysis`, `Review` y `IntelThreatLink`.
5. `Run` / `RunItem`: registra periodos de monitoreo; cada `RunItem` indica qué `IntelItem` apareció en esa corrida.
6. `AIAnalysis`: resumen generado por IA, marcado con prioridad y acciones recomendadas.
7. `Report`: comunicado mensual; se genera desde una `Run` y puede incluir PDF/HTML/Markdown.
8. `Review`: decisión humana (aprobar, monitorear, crear ticket) asociada a `IntelItem` y `Run`.
9. `IntelThreatLink`: vincula un `IntelItem` con un `resources.Threat`, reutilizando el catálogo de riesgos.

## Vistas principales
- **Corridas (`Run`):** `RunListView`, `RunDetailView`, `RunRerunView`, `RunExportView`, `RunItemListView` (docstrings en español). muestran listas, detalles, reanálisis y exportaciones de cada ciclo.
- **IntelItem:** `IntelItemDetailView`, `IntelItemToggleRelevantView`, `LinkThreatView`, `search_threats_ajax` (nuevos docstrings) permiten revisar, marcar relevancia y vincular amenazas.
- **Análisis IA:** `AIAnalysisListView`, `AIAnalysisDetailView`, `AIAnalysisRerunView`, `AIAnalysisExportView` resumen y re-ejecutan modelos sobre cada item.
- **Reportes:** `ReportListView`, `ReportDetailView`, `ReportCreateView`, `ReportSendView` cubren creación, previsualización y envío.
- **Revisiones:** `ReviewCreateView`, `ReviewListView`, `ReviewDetailView`, `ReviewUpdateView` registran/quitan decisiones de gestión.
- **Configuración:** vistas CRUD para `Source` y `TechTag`, junto con `ConfigView` que muestra métricas agregadas.

## URLs relevantes
- `runs/` (listado), `runs/<pk>/` (detalle), `runs/<pk>/rerun`, `runs/<pk>/export`
- `runs/<run_pk>/items/` (items por corrida)
- `items/<pk>/`, `items/<pk>/toggle-relevant/`, `items/<pk>/link-threat/`, `ajax/search-threats/`
- `analyses/`, `reports/`, `reviews/`, `config/`, `sources/`, `techtags/`

## Servicios auxiliares
- `services/ai.py`: lógica para normalizar ítems y consultar OpenAI (análisis y reanálisis).
- `services/emailer.py`: envíos de reportes por SMTP o Brevo con adjuntos.
- `services/report_generator.py`: exporta reportes como PDF/Markdown/JSON.

## Relación con otros módulos
- `IntelThreatLink` reutiliza `resources.Threat` para mantener catálogos sincronizados.
- Los reportes pueden enviarse a usuarios definidos en `resources` (ej. `CustomUser`).

## Diagramas
- El grafo de entidad-relación se documenta en `ER_RELATIONSHIP.md` para visualizar herencias y dependencias críticas (`Run`, `IntelItem`, `AIAnalysis`, `Report`, `Review`).
