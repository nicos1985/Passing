# Documentación de la app `permission`

## Propósito
La app `permission` gestiona permisos de acceso entre usuarios y contraseñas (`ContraPermission`), define
roles de permiso reutilizables (`PermissionRoles`) y asigna roles a usuarios (`UserRoles`).

## Flujos principales
- Asignación individual: `seleccionar_usuario` → `gestion_permisos` permite editar permisos por contraseña para un usuario.
- Roles: `PermissionRolesCreateView` / `PermissionRolUpdate` permite agrupar contraseñas y luego asignarlas con `assign_rol_user`.
- Auditoría/diagnóstico: `users_audit` genera un reporte con diferencias entre rol y permisos asignados.

## Modelos clave
- `ContraPermission`: vincula `CustomUser` con `Contrasena` para permisos explícitos.
- `PermissionRoles`: colecciones de `Contrasena` que simplifican asignaciones masivas.
- `UserRoles`: persistencia de la relación usuario→rol.

## Formularios
- `PermisoForm`: genera dinámicamente campos Checkbox por cada `Contrasena` pública.
- `PermissionRolesForm`, `UserRolForm`: formularios para crear roles y asignarlos.

## Notas para desarrolladores
- Varias vistas usan `user_passes_test` para restringir a administradores.
- `generate_rol_permissions` elimina permisos previos del usuario (excepto contraseñas personales) antes de aplicar los del rol.
