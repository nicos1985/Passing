# Pruebas locales en Windows

El entorno usa Python 3.12 en `.venv`, la configuración `passing.local` y una base
vacía en `.local/db.sqlite3`. No utiliza ni modifica `db.sqlite3`. El entorno viejo
`env` se conserva, pero ya no se usa para estas pruebas.

## Iniciar

Desde PowerShell, en la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

Abrir http://127.0.0.1:8000/login/. También se puede iniciar desde VS Code con la
configuración **Passing local (2FA)** y F5. Para detenerlo, Ctrl+C en la terminal.

Si el servidor quedó iniciado en segundo plano durante la preparación, detenerlo
antes de abrir otro en el mismo puerto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

Las credenciales están en `.local/accounts.txt`, excluido de Git:

- `admin_local`: superadministrador para probar configuración y recuperación.
- `admin_respaldo`: segundo superadministrador para recuperar al primero.
- `usuario_local`: cuenta común.

Al primer ingreso cada cuenta debe escanear su propio QR en Google Authenticator y
confirmar un código. Al cerrar sesión y volver a ingresar debe solicitar otro
código. Si acabás de usar uno, esperá al siguiente: no se permite reutilizarlo.

Para probar recuperación, ingresar como administrador, abrir la lista de usuarios
y pulsar **Recuperar 2FA** en otra cuenta. Confirmar con la contraseña y un código
nuevo del administrador. La cuenta recuperada debe volver a configurar su QR.

## Particularidades locales

- El login local omite reCAPTCHA; la verificación TOTP sigue activa. Producción
  conserva reCAPTCHA. No usar `passing.local` para ejecutar producción.
- Los correos se imprimen en la terminal: para probar reset de contraseña, abrir
  el enlace que aparece allí. No se envían correos reales.
- Los logs quedan en `.local/debug.log` y la terminal.
- El servidor escucha solamente en `127.0.0.1`. El teléfono puede escanear el QR
  de la pantalla sin conectarse al servidor local.
- La base empieza vacía y contiene solamente las cuentas de prueba.

## Preparar de nuevo o instalar dependencias

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local.ps1
```

Requiere `uv`, `passing/settings.py` y `passing/config.py`, presentes en este equipo.
El script es repetible: no reinicia las contraseñas ni el 2FA de usuarios existentes.
La política de ejecución se cambia solamente para ese proceso de PowerShell.

## Pruebas automáticas

```powershell
.\.venv\Scripts\python.exe manage.py test passbase login securitycontrol --settings=passing.test_settings
```

## Actualización de seguridad

La migración `securitycontrol.0001_initial` incorpora los límites de intentos.
Ejecutar `setup-local.ps1` al actualizar otro entorno local. La sesión conserva
24 horas absolutas; la nueva clave de firma local invalida sesiones anteriores,
pero conserva usuarios y dispositivos OTP. Las correcciones y los pasos para
Ubuntu están en [security-hardening.md](security-hardening.md).
