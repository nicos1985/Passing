# Documentación — App `docmanager`

## Tabla de contenidos

1. [Propósito](#propósito)
2. [Dependencias externas](#dependencias-externas)
3. [Modelos](#modelos)
   - [IntegrationCredential](#integrationcredential)
   - [DocumentoControlado](#documentocontrolado)
4. [Servicios (`services.py`)](#servicios-servicespy)
5. [Formularios (`forms.py`)](#formularios-formspy)
6. [Vistas (`views.py`)](#vistas-viewspy)
7. [URLs (`urls.py`)](#urls-urlspy)
8. [Tareas Celery (`tasks.py`)](#tareas-celery-taskspy)
9. [Admin (`admin.py`)](#admin-adminpy)
10. [Templates](#templates)
11. [Interacción entre componentes](#interacción-entre-componentes)
12. [Lógica de cumplimiento y semáforo](#lógica-de-cumplimiento-y-semáforo)
13. [Flujo de sincronización con Drive](#flujo-de-sincronización-con-drive)
14. [Flujo de notificaciones push (webhooks)](#flujo-de-notificaciones-push-webhooks)
15. [Pendientes y próximas funcionalidades](#pendientes-y-próximas-funcionalidades)

---

## Propósito

`docmanager` gestiona la integración con **Google Drive** para llevar un registro de *documentos controlados*: archivos de Drive que deben revisarse periódicamente según una política configurable (por defecto cada **90 días**, próximamente configurable desde la clase de configuración global o `settings`).

El módulo permite:

- Almacenar y cifrar credenciales de Service Account de Google Drive.
- Navegar carpetas de Drive desde la interfaz web.
- Consultar metadata y revisiones de archivos individuales.
- Mantener registros locales (`DocumentoControlado`) sincronizados con Drive.
- Calcular el estado de cumplimiento de revisión de cada documento (semáforo verde/amarillo/rojo).
- Recibir notificaciones push de Google Drive vía webhooks.
- Exponer una API JSON de insights para dashboards.

---

## Dependencias externas

| Paquete | Uso |
|---|---|
| `google-auth` | Autenticación OAuth2 con Service Account |
| `google-api-python-client` | Cliente Drive API v3 (`googleapiclient`) |
| `celery` | Tareas asincrónicas (`@shared_task`) |
| `passbase.crypto` | Cifrado/descifrado Fernet para secretos |

---

## Modelos

### `IntegrationCredential`

Almacena las credenciales de acceso a servicios externos (actualmente solo Google Drive). El JSON del Service Account se guarda **cifrado con Fernet** en `secret_encrypted`.

```
IntegrationCredential
├── name                CharField(128)      — Nombre visible (ej: "Credencial producción GDrive")
├── service             CharField           — Choices: google_drive
├── status              CharField           — Choices: active | inactive | revoked  (default: active)
├── key_id              CharField(128)      — Identificador interno opcional
├── secret_encrypted    TextField           — JSON del Service Account cifrado con Fernet
├── created_by          FK → AUTH_USER_MODEL (nullable)
├── created_at          DateTimeField auto
└── updated_at          DateTimeField auto
```

**Métodos y propiedades relevantes:**

| Nombre | Tipo | Descripción |
|---|---|---|
| `is_active` | property | `True` si `status == "active"` |
| `set_secret(raw)` | method | Cifra el secreto y lo guarda en `secret_encrypted` |
| `get_secret()` | method | Descifra y devuelve el JSON como string, o `None` |
| `masked_secret()` | method | Versión enmascarada para mostrar en admin (no descifra) |

---

### `DocumentoControlado`

Representa un archivo de Google Drive trackeado por la política de documentos controlados. Se crea o actualiza automáticamente cuando se listan carpetas o se sincronizan archivos.

```
DocumentoControlado
├── drive_file_id           CharField(255) unique — ID nativo de Drive
├── carpeta_drive_id        CharField(255)        — ID de la carpeta padre en Drive
├── credencial              FK → IntegrationCredential (nullable)
├── nombre_archivo          CharField(255)        — Nombre del archivo en Drive
├── link_edicion            URLField             — webViewLink de Drive
├── ultima_sincronizacion   DateTimeField        — Última vez que sincronizamos desde Drive
├── fecha_modificacion_drive DateTimeField       — modifiedTime devuelto por Drive API
├── ultimo_editor_drive     CharField(255)        — displayName o email del último editor
├── frecuencia_revision_dias PositiveIntegerField default 90 — Ciclo de revisión en días
├── no_encontrado           BooleanField          — True si el archivo fue eliminado/no accesible
├── created_at              DateTimeField auto
└── updated_at              DateTimeField auto
```

**Propiedades de cumplimiento:**

| Nombre | Tipo | Descripción |
|---|---|---|
| `dias_restantes` | property → `int\|None` | Días hasta el vencimiento del ciclo de revisión. Negativo cuando ya venció. `None` si no hay `fecha_modificacion_drive`. |
| `estado_cumplimiento` | property → `str` | Devuelve uno de: `al_dia`, `proximo`, `vencido`, `no_encontrado`, `sin_datos` |
| `semaforo_color` | property → `str` | Color hexadecimal según el estado (verde/amarillo/rojo/gris) |

**Lógica de estados:**

```
no_encontrado == True          → "no_encontrado"  (gris #6b7280)
fecha_modificacion_drive es None → "sin_datos"    (gris claro #9ca3af)
(fecha_modificacion + frecuencia_revision_dias) <= ahora → "vencido" (rojo #e34f4f)
remaining <= min(20% del período, 7 días)          → "proximo"  (amarillo #f6c344)
resto                                               → "al_dia"   (verde #18a558)
```

**Método:**

| Nombre | Descripción |
|---|---|
| `apply_drive_metadata(metadata: dict)` | Actualiza campos locales desde un dict de respuesta de Drive API |

---

## Servicios (`services.py`)

### Jerarquía de excepciones

```
GoogleDriveServiceError
├── InvalidCredential      — Credencial inexistente, inactiva o sin secreto
└── DriveFileNotFound      — Archivo eliminado o inaccesible en Drive
```

### `GoogleDriveService`

Wrapper sobre Google Drive API v3. Se instancia con una `IntegrationCredential` activa.

```python
service = GoogleDriveService(credential)
```

**Métodos:**

| Método | Descripción |
|---|---|
| `_client()` | Construye y cachea el cliente `googleapiclient`. Descifra el secreto, crea `Credentials` de Service Account. |
| `fetch_metadata(file_id)` | Consulta campos `id, name, mimeType, modifiedTime, webViewLink, lastModifyingUser` de un archivo. |
| `listar_carpeta(carpeta_id)` | Lista todos los archivos no eliminados de una carpeta. Por cada ítem llama `_apply_drive_item` para hacer upsert local. |
| `_apply_drive_item(item, carpeta_id)` | Hace `update_or_create` de `DocumentoControlado` dentro de una transacción atómica. |
| `sync_file(file_id)` | Llama `fetch_metadata` + `_apply_drive_item`. Devuelve el `DocumentoControlado` actualizado. |
| `sync_documento(doc)` | Sincroniza un `DocumentoControlado` existente. Marca `no_encontrado=True` si recibe 404. |
| `watch_file(file_id, webhook_url, ...)` | Registra un canal de notificaciones push en Google Drive. |
| `list_revisions(file_id)` | Devuelve historial de revisiones del archivo (id, modifiedTime, editor, tamaño, etc.). |
| `about()` | Devuelve información de la cuenta Drive (usuario, cuota de almacenamiento). |

### Helpers de módulo

```python
sync_file(file_id, credential)    # Atajo: instancia servicio + sync_file
sync_folder(carpeta_id, credential)  # Atajo: instancia servicio + listar_carpeta
```

---

## Formularios (`forms.py`)

### `IntegrationCredentialForm`

`ModelForm` para crear/actualizar una `IntegrationCredential` desde la interfaz web.

**Campo adicional:** `secret_plain` (`CharField`/`Textarea`) — acepta el JSON del Service Account en texto plano. El formulario lo cifra automáticamente al guardar mediante `set_secret()`.

- En **creación**: `secret_plain` es obligatorio.
- En **edición**: `secret_plain` es opcional; si se deja vacío, el secreto existente no cambia.
- `save()` fuerza `service = GOOGLE_DRIVE` antes de guardar.

---

## Vistas (`views.py`)

### `drive_webhook_receiver`

| Atributo | Valor |
|---|---|
| URL | `docmanager/webhook/drive/` |
| Método | `POST` únicamente |
| Auth | Ninguna (endpoint público, `@csrf_exempt`) |
| Name | `docmanager:drive_webhook` |

Recibe notificaciones push de Google Drive. Lee los headers:
- `X-Goog-Resource-Id` — ID del archivo que cambió
- `X-Goog-Channel-Id` — ID del canal de notificación
- `X-Goog-Resource-State` — Estado del recurso (`sync`, `update`, etc.)

Encola `process_drive_change.delay(...)` y responde `204 No Content` inmediatamente.

---

### `DocumentInsightsView`

| Atributo | Valor |
|---|---|
| URL | `docmanager/insights/` |
| Método | `GET` |
| Auth | Ninguna ⚠️ (ver nota de seguridad abajo) |
| Name | `docmanager:insights` |

Devuelve un JSON con el resumen de cumplimiento:

```json
{
  "resumen": { "al_dia": 3, "proximo": 1, "vencido": 2, "sin_datos": 0, "no_encontrado": 0 },
  "highlights": ["Tienes 2 documentos vencidos.", "Tienes 1 documento próximo a vencer."],
  "documentos": [
    {
      "id": 1, "nombre": "Procedimiento ISO", "estado": "vencido",
      "color": "#e34f4f", "link_edicion": "...", "dias_restantes": -5
    }
  ]
}
```

Acepta `?carpeta=<carpeta_drive_id>` para filtrar por carpeta.

> ⚠️ **Nota de seguridad:** Esta vista no requiere autenticación. Si los nombres/links de documentos son sensibles, considerar agregar `@login_required`.

---

### `drive_credential_view`

| Atributo | Valor |
|---|---|
| URL | `docmanager/config/drive/` |
| Método | `GET` / `POST` |
| Auth | `@login_required` + staff/superuser |
| Name | `docmanager:drive_config` |

Formulario para cargar o actualizar la credencial de Google Drive. En edición muestra el formulario con la credencial más reciente pre-cargada.

---

### `drive_status_view`

| Atributo | Valor |
|---|---|
| URL | `docmanager/config/drive/status/` |
| Método | `GET` |
| Auth | `@login_required` + staff/superuser |
| Name | `docmanager:drive_status` |

Muestra el estado de la credencial activa. Si se añade `?probar=1` en la URL, llama a `service.about()` para verificar conectividad en vivo y devuelve información de la cuenta (usuario, cuota).

---

### `drive_browser_view`

| Atributo | Valor |
|---|---|
| URL | `docmanager/config/drive/browse/` |
| Método | `GET` |
| Auth | `@login_required` + staff/superuser |
| Name | `docmanager:drive_browse` |

Explorador de carpetas de Drive. Parámetros de query string:

| Param | Default | Descripción |
|---|---|---|
| `folder` | `root` | ID de la carpeta a listar |
| `name` | `root` | Nombre de la carpeta actual (para breadcrumb) |
| `path` | `[]` | JSON del histórico de navegación (breadcrumb trail) |

Al listar carpeta, llama a `service.listar_carpeta()` que hace el upsert de `DocumentoControlado` automáticamente. Incluye iconos Font Awesome según MIME type (carpeta, Google Docs, Sheets, PDF, imagen, etc.).

---

### `drive_revisions_view`

| Atributo | Valor |
|---|---|
| URL | `docmanager/config/drive/revisions/` |
| Método | `GET` |
| Auth | `@login_required` + staff/superuser |
| Name | `docmanager:drive_revisions` |

Muestra el historial de revisiones de un archivo específico. Requiere `?file_id=<id>`. Humaniza tamaños de archivo y timestamps para la UI.

---

## URLs (`urls.py`)

```
app_name = "docmanager"

Prefijo global (en urls_tenant.py): docmanager/

Ruta completa                              Nombre                    Vista
─────────────────────────────────────────────────────────────────────────────
docmanager/webhook/drive/                  drive_webhook             drive_webhook_receiver
docmanager/config/drive/                   drive_config              drive_credential_view
docmanager/config/drive/status/            drive_status              drive_status_view
docmanager/config/drive/browse/            drive_browse              drive_browser_view
docmanager/config/drive/revisions/         drive_revisions           drive_revisions_view
docmanager/insights/                       insights                  DocumentInsightsView
```

---

## Tareas Celery (`tasks.py`)

### `process_drive_change(resource_id, channel_id, state)`

Disparada por el webhook. Busca el `DocumentoControlado` por `drive_file_id`. Si no existe, termina sin error. Si existe, obtiene la credencial (del doc o la activa global) y llama `service.sync_documento()`. En caso de 404 marca `no_encontrado=True`.

### `check_vencimientos()`

Tarea periódica pensada para ejecutarse con Celery Beat (ej: diariamente). Itera todos los documentos, cuenta por `estado_cumplimiento` y registra en el log los documentos `vencido` o `proximo`.

Devuelve un dict resumen:
```python
{"vencido": 2, "proximo": 1, "al_dia": 10, "sin_datos": 3, "no_encontrado": 0}
```

> ⚠️ **TODO:** Integrar con el módulo `notifications` para enviar alertas a los responsables.

---

## Admin (`admin.py`)

### `IntegrationCredentialAdmin`

- Listado: nombre, servicio, estado, key_id, secreto enmascarado, fecha actualización.
- Filtros: servicio, estado.
- Búsqueda: nombre, key_id.
- Readonly: created_at, updated_at, masked_secret.
- Usa `IntegrationCredentialAdminForm` para aceptar `secret_plain` y cifrarlo al guardar.

### `DocumentoControladoAdmin`

- Listado: nombre, drive_file_id, estado_cumplimiento, última sincronización, fecha modificación Drive, frecuencia revisión, no_encontrado.
- Filtros: no_encontrado, credencial.
- Búsqueda: nombre, drive_file_id.
- Readonly: ultima_sincronizacion, fecha_modificacion_drive, created_at, updated_at.
- Autocomplete en campo credencial.

---

## Templates

Los templates viven en el directorio **global** `templates/docmanager/`:

| Template | Vista asociada | Descripción |
|---|---|---|
| `drive_credential_form.html` | `drive_credential_view` | Formulario de carga de credencial |
| `drive_status.html` | `drive_status_view` | Estado de la conexión + info de cuenta |
| `drive_browser.html` | `drive_browser_view` | Explorador de carpetas con breadcrumb e iconos |
| `drive_revisions.html` | `drive_revisions_view` | Historial de revisiones de un archivo |

---

## Interacción entre componentes

```
Usuario (staff)
    │
    ├─► drive_credential_view  ──► IntegrationCredentialForm ──► IntegrationCredential
    │                                                               │ (secret cifrado)
    │
    ├─► drive_status_view  ──────► GoogleDriveService.about()
    │
    ├─► drive_browser_view  ─────► GoogleDriveService.listar_carpeta()
    │                                    │
    │                                    └──► _apply_drive_item() ──► DocumentoControlado (upsert)
    │
    └─► drive_revisions_view  ───► GoogleDriveService.list_revisions()


Google Drive (push)
    │
    └──► drive_webhook_receiver  ──► process_drive_change.delay()
                                           │
                                           └──► GoogleDriveService.sync_documento()
                                                       │
                                                       └──► DocumentoControlado (update)


Celery Beat (periódico)
    │
    └──► check_vencimientos()  ──► DocumentoControlado.estado_cumplimiento
                                           │
                                           └──► (TODO) notifications app


Dashboard/Frontend
    │
    └──► DocumentInsightsView (JSON API)
              │
              └──► DocumentoControlado.estado_cumplimiento / semaforo_color / dias_restantes
```

---

## Lógica de cumplimiento y semáforo

El campo clave es `frecuencia_revision_dias` en `DocumentoControlado` (default: **90 días**).

El vencimiento se calcula como:

```
fecha_vencimiento = fecha_modificacion_drive + frecuencia_revision_dias
dias_restantes    = fecha_vencimiento - ahora
```

### Estados y colores

| Estado | Condición | Color |
|---|---|---|
| `al_dia` | `dias_restantes > umbralAmarillo` | Verde `#18a558` |
| `proximo` | `dias_restantes <= min(20% del período, 7 días)` | Amarillo `#f6c344` |
| `vencido` | `dias_restantes <= 0` | Rojo `#e34f4f` |
| `no_encontrado` | `no_encontrado == True` | Gris `#6b7280` |
| `sin_datos` | Sin `fecha_modificacion_drive` | Gris claro `#9ca3af` |

### Configuración de la frecuencia

Actualmente `frecuencia_revision_dias` se define por documento. El plan es agregar un valor por defecto global configurable desde `settings` o una clase de configuración (ej: `settings.DOCMANAGER_FRECUENCIA_REVISION_DIAS = 365`) que se aplique como default al crear nuevos `DocumentoControlado`.

---

## Flujo de sincronización con Drive

### Al navegar carpeta

```
1. drive_browser_view → GoogleDriveService.listar_carpeta(folder_id)
2. Drive API: files().list(q="'folder_id' in parents and trashed=false")
3. Por cada archivo devuelto:
   - _apply_drive_item() → DocumentoControlado.update_or_create(drive_file_id=...)
   - Actualiza: nombre, link, fecha modif, editor, carpeta, credencial
   - Marca ultima_sincronizacion = now()
   - Marca no_encontrado = False
```

### Al recibir webhook

```
1. Google Drive → POST /docmanager/webhook/drive/
2. drive_webhook_receiver lee headers X-Goog-Resource-Id / State / Channel-Id
3. Encola process_drive_change.delay(resource_id, ...)
4. Responde 204 inmediatamente (no bloquea)
5. [Celery worker] process_drive_change:
   - Busca DocumentoControlado por drive_file_id
   - Obtiene credencial activa
   - GoogleDriveService.sync_documento(doc)
   - Si 404 → no_encontrado = True
```

---

## Flujo de notificaciones push (webhooks)

Para activar notificaciones push de Drive hacia el endpoint propio:

```python
service.watch_file(
    file_id="<drive_file_id>",
    webhook_url="https://tudominio.com/docmanager/webhook/drive/",
    channel_id="<uuid>",     # generado automáticamente si no se pasa
    expiration_ms=604800000  # 7 días en ms (máximo permitido por Drive)
)
```

Drive enviará `POST /docmanager/webhook/drive/` cada vez que el archivo cambie. Los canales expiran y deben renovarse.

---

## Pendientes y próximas funcionalidades

1. **Configuración global de frecuencia:** Agregar `settings.DOCMANAGER_FRECUENCIA_REVISION_DIAS` (default 365) y usarlo como `default` al crear `DocumentoControlado` en `_apply_drive_item`.

2. **Panel de pendientes:** Vista/página que muestre los documentos con estado `vencido` y `proximo`, filtrable por carpeta, responsable, etc.

3. **Integración con `notifications`:** En `check_vencimientos()`, enviar notificaciones (email, in-app) a los responsables de los documentos vencidos/próximos.

4. **Renovación automática de canales webhook:** Tarea periódica que llame `watch_file` antes de que expiren los canales.

5. **Autenticación en `DocumentInsightsView`:** Agregar `@login_required` para proteger la exposición de nombres y links de documentos.

6. **Asignación de responsables:** Campo `responsable` en `DocumentoControlado` para saber a quién notificar.

7. **Historial de revisiones local:** Guardar en BD cada revisión que llega de Drive para auditoría sin depender de la API en cada consulta.
