# Documentación de la app `notifications`

## Propósito general
`notifications` registra alertas sobre contraseñas: los usuarios comunes reciben avisos cuando algo requiere su atención y los administradores/staff reciben solicitudes para compartir contraseñas con un usuario específico.

## Flujos principales
1. **Solicitar compartir una contraseña**: `share_contrasena_form` valida el formulario `CreateNotificationForm`, crea un `AdminNotification` si el usuario no tiene permiso previo y notifica al solicitante del estado (ya compartido, solicitud repetida o creada). El formulario se sirve en `create-noti-admin.html`.
2. **Visualizar notificaciones**: `ListNotificationsUser` muestra las filas de `UserNotifications` filtradas por el usuario logueado; se ordenan para que las no vistes aparezcan primero. `MarkNotificationsViewed` expone un endpoint AJAX para marcar todas como vistas.
3. **Gestión administrativa**: `ListNotificationsAdmin` lista las solicitudes (viewed, created). `AdminNotification` incluye tipo de usuario, acción realizada y comentario.

## Modelos clave
- `UserNotifications`: notificaciones simples asociadas a un `CustomUser` y una `Contrasena` para que los usuarios puedan seguir acciones o invitaciones.
- `AdminNotification`: solicitudes que se envían a admins/staff y registran qué contraseña se comparte, quién lo solicitó y qué acción está pendiente.
- `UserType`: define si la notificación administrativa va al staff o a admins.

## Formularios y validaciones
- `CreateNotificationForm`: permite al solicitante elegir al usuario receptor activo del tenant y dejar un comentario sobre la solicitud. Usa `CustomUser.for_current_tenant()` para asegurarse de que sólo se elijan usuarios válidos.

## Permisos y helpers
- `can_view_contrasena` valida que el usuario tenga permisos sobre la contraseña antes de permitir la solicitud.
- `is_administrator` limita el acceso a las vistas administrativas.

## URLs relevantes
| Ruta | Vista | Propósito |
| --- | --- | --- |
| `/notifications/share/<contrasena>/` | `share_contrasena_form` | Envía la solicitud a admins para compartir una contraseña con otro usuario.
| `/notifications/user/` | `ListNotificationsUser` | Lista las notificaciones que el usuario aún debe revisar.
| `/notifications/mark-viewed/` | `MarkNotificationsViewed` | Endpoint AJAX que marca todas las notificaciones como vistas.
| `/notifications/admin/` | `ListNotificationsAdmin` | Muestra a los administradores las solicitudes pendientes.

## Notas adicionales
- Por ahora `UpdateNotificationsUser` y `UpdateNotificationsAdmin` son placeholders y pueden extenderse para editar o borrar notificaciones.
- El módulo no tiene lógica compleja de email; se apoya en formularios y en la manipulación de flags `viewed` para mostrar el estado.
