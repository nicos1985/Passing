# Documentación de la app `passbase`

## Propósito
`passbase` contiene los modelos y vistas para administrar contraseñas cifradas por tenant,
secciones temáticas y un sistema simple de auditoría (`LogData`).

## Flujos principales
- Crear/editar/eliminar contraseñas: las vistas (`ContrasCreateView`, `ContrasUpdateView`, `ContrasDeleteView`) gestionan cifrado antes de persistir y crean entradas en `LogData`.
- Visualización: `ContrasListView` y `ContrasDetailView` desencriptan los campos para la UI solo en RAM; los valores se almacenan cifrados en la base.
- Importación masiva: `upload_csv` y `CSVUploadForm` permiten subir CSVs. `bulk_create_with_logs` crea registros en bloque y logs asociados.
- Operaciones de mantenimiento: vistas/funciones para encriptar historial, rollback y generación de hashes.

## Modelos clave
- `Contrasena`: almacena credenciales cifradas, `owner`, `is_personal`, `actualizacion` y `hash` para detectar duplicados.
- `SeccionContra`: agrupa contraseñas por sección.
- `LogData`: registro de auditoría que guarda acciones y detalles (los campos sensibles pueden estar cifrados).

## Formularios
- `ContrasenaForm`, `ContrasenaUForm`: formularios para crear/editar contraseñas; `ContrasenaUForm` acepta `decrypted_user` y `decrypted_password` para inicializar campos.
- `CSVUploadForm`: para subir archivos CSV en importaciones masivas.

## Seguridad y cifrado
- El módulo usa `passbase.crypto` para cifrar/descifrar datos con `Fernet`. La clave debe definirse en `settings.CRYPTOGRAPHY_KEY`.
- Nunca loguear contraseñas en texto plano; `LogData` almacena referencia y, cuando sea necesario, datos cifrados.

## URLs relevantes
- `listpass`, `createpass`, `updatepass`, `deletepass`, `detailpass` (ver `passbase/urls.py`).

## Notas para desarrolladores
- `scraping.py` es prototipo y no debería usarse en producción.
- `signals.py` está preparado para receptores; agregar `@receiver` cuando se desee auditar eventos adicionales.
