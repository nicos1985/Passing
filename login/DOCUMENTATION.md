# Documentación de la app `login`

## Propósito general
`login` sirve como interfaz tenant-aware para acceder al dashboard, crear usuarios (incluyendo superusuarios), proteger el acceso con 2FA/SSO y exponer formularios administrativos. El hub público usa algunas de estas vistas y el tenant activo reutiliza helpers para validar pertenencia.

## Flujos relevantes
1. **Alias públicos**: `/login/` redirige al dashboard con `login_alias_to_home`, mientras que `login_alias_to_hub` envia al hub externo (`accounts`) preservando `next`.
2. **Dashboard tenant**: `home_tenant` compila métricas de treatments, riesgos y alerta de threat intelligence para usuarios autenticados con permiso.
3. **Registro y superusuarios**: `register` crea usuarios asociados al tenant actual con email de activación, mientras que `create_superuser` genera el primer admin y dispara el email de bienvenida.
4. **2FA y QR**: `verify_2fa`, `show_qr_code_2fa` y los helpers `send_qr_code_email_inline/cid` orquestan el enrolamiento y la verificación del TOTP. El middleware `TwoFactorAuthMiddleware` impide el acceso si no se completa la verificación.
5. **SSO**: `sso_consume` recibe el token firmado desde el hub, valida membresías y decide si obliga a 2FA antes de loguear con `_login_with_backend`.

## Formularios y validaciones
- `CustomLoginForm` y `AdminLoginForm` usan `ReCaptchaV3` para mitigar bots.
- `UserForm` y `UserDepartureForm` alimentan las vistas de admin para crear/editar/baja de usuarios.
- `GlobalSettingsForm` permite configurar políticas globales del tenant: 2FA masivo, color de menú y administradores designados.
- `ProfileForm` gestiona avatar, datos de contacto y la habilitación individual de 2FA.

## Modelos clave
- `CustomUser`: Extiende `AbstractUser` incluyendo avatar, OTP, y flags para 2FA, además de métodos como `formatted_birth_date` y `has_otp_secret`.
- `GlobalSettings`: Guarda la política de multifactor, dashboard activo, color, admin designados y se accede desde `GlobalSettingsUpdateView`.
- `MultifactorChoices`: Enumera los estados del segundo factor (desactivado, activado, elección del usuario).

## Seguridad y reutilización
- `TenantScopedUserMixin` y `Safe404RedirectMixin` aseguran que los CBV sólo manipulan usuarios del tenant actual y que los 404 se muestran con mensajes amigables.
- `require_tenant_membership` (de `accounts`) se complementa con `user_belongs_to_current_tenant` para doble verificación en acciones sensibles.
- Las vistas usan `user_passes_test` para limitar las operaciones de baja/activación a administradores.

## URLs principales
| Ruta | Propósito |
| --- | --- |
| `/login/home/` | Dashboard con métricas e indicios de threat intelligence.
| `/login/register/` | Crea usuarios dentro del tenant actual.
| `/login/<schema>/create-superuser/` | Crea el primer admin y envía email de activación.
| `/login/profile/` | Actualiza avatar, datos y opciones de 2FA.
| `/login/verify-2fa/` | Valida el TOTP cuando el middleware lo exige.
| `/login/show-qr-code-2fa/` | Muestra el código QR para enrolar 2FA.
| `/login/sso/consume/` | Endpoint que acepta tokens SSO firmados.
| `/login/users/`, `/login/update-user/<pk>` | Gestión admin de usuarios (lista, actualización, detalle, baja, activación).

## Notas adicionales
- `GlobalSettingsUpdateView.activate_multifactor_for_all` y `deactivate_multifactor_for_all` sincronizan el estado global de 2FA y envían el QR por email.
- Los helpers `generate_qr_bytes`/`generate_qr_base64` se reutilizan en `send_qr_code_email_inline` y `send_qr_code_email_cid`, lo que evita duplicar la lógica de creación de imágenes.
- Si se introduce otro proveedor de login, basta con adaptar `sso_consume`, la configuración `SSO_LOGIN_BACKEND` y, si es necesario, extender `TwoFactorAuthMiddleware`.
