# Documentación de la app `accounts`

## Propósito general
`accounts` se encarga del hub público de autenticación: login tradicional, ingresos vía Google OAuth y la distribución de usuarios entre tenants (clientes) compartidos mediante `django-tenants`. También contiene los modelos que extienden el usuario público (`CustomUser`) y guardan eventos de autenticación y políticas por cliente.

## Flujos principales
1. **Login del hub**: `login_view` valida `HubLoginForm`, autentica con `EmailOrUsernameBackend` y, si el usuario tiene 1+ memberships activas, se redirige al tenant con `redirect_to_tenant_with_token`. Si hay multiples memberships muestra `choose_tenant_view`.
2. **Google OAuth**: `google_start` registra `client_slug`, `next_path` y genera `_s` antes de llamar al endpoint de allauth. `post_login_redirect` valida el estado (`_s` o datos en sesión) y condiciona el flujo entre selector de tenant o redirección directa al SSO del tenant resolviendo dominio vía `_resolve_tenant_base_url`. `google_start_auto` inicia el proceso sin `client` y deja que `post_login_redirect` seleccione el tenant final.
3. **Utilitarios**: `build_oauth_state`, `build_sso_token`, `resolve_primary_domain` y `_port_from_request` apoyan el armado seguro de URLs y tokens. `get_memberships_for_email`, `get_ip` y `get_ua` centralizan datos reutilizados en adaptadores y eventos.

## Modelos clave
- `CustomUser`: Extiende `AbstractUser` con campos de perfil, helpers tenant-aware (`for_client`, `for_current_tenant`) y `assigned_role` seguro. Está vinculado a instancias públicas de `client.Client`.
- `TenantMembership`: Vincula `CustomUser` con `Client`, registra rol macro y estado. Es el vínculo que define quién puede acceder a qué tenant.
- `TenantSettings`: OneToOne con `Client` para configurar SSO, recordatorios y apariencia del dashboard.
- `AuthEvent`: Registra intentos de login (password, google, SSO) y ayuda a auditar errores/consumos.

Desarrolladores externos deben saber que `CustomUser.client` siempre referencia al modelo público de `Client`, mientras que el resto de los models se resuelve desde ese esquema compartido.

## URLs públicas
| Ruta | Vista | Propósito |
| --- | --- | --- |
| `/accounts/` | `login_view` | Login tradicional del hub.
| `/accounts/google/start/` | `google_start` | Guarda client y next antes de arrancar OAuth.
| `/accounts/google/start-auto/` | `google_start_auto` | Inicia Google OAuth sin client.
| `/accounts/post-login/` | `post_login_redirect` | Nodo de regreso donde se resuelve el tenant.
| `/accounts/choose-tenant/` | `choose_tenant_view` | Selector cuando hay varias memberships.
| `/accounts/logout/` | `logout_view` | Cierra sesión en el hub y regresa al login.

## Admin y adaptadores
- `TenantMembershipAdmin`, `TenantSettingsAdmin`, `CustomUserAdmin` y `AuthEventAdmin` permiten filtrar/mirar estado 2FA, roles, SSO y audit logs desde el sitio público.
- `AccountAdapter` bloquea el signup de allauth, `SocialAdapter` vincula logins de Google con `CustomUser` existentes y registra eventos.
- El decorator `require_tenant_membership` protege vistas internas asegurándose de que el request.user tenga una membership activa para el tenant actual.

## Comando de utilidad
`setup_google_oauth` crea o actualiza el `SocialApp` de Google asignado al `Site` actual. Se usa en despliegues para sincronizar credenciales antes de habilitar el login social.

## Notas adicionales
- Las utilidades `redirect_to_tenant_with_token`, `build_oauth_state` y `build_sso_token` exportan la lógica necesaria para generar URLs absolutos sin duplicar reglas.<br>
- Si se expande el hub hacia otros proveedores, conviene extender `SocialAdapter` y los eventos en `AuthEvent` para mantener auditoría centralizada.
- Este módulo no contiene lógica de usuarios dentro de tenants; solo mueve usuarios desde PUBLIC a esquemas clientes y documenta qué tenant tiene acceso a quién.
