# Correcciones de seguridad — 17/09/2026

El informe `security-review-2026-09-17.md` describe el estado **anterior** a estos cambios.
Las reproducciones se convirtieron en pruebas de regresión que ahora exigen bloquear
los accesos indebidos. Las correcciones se aplicaron al código local; no se accedió
al Ubuntu de producción.

## Cambios

| Hallazgo | Corrección |
|---|---|
| S01, S02, S06: acceso a credenciales y adjuntos ajenos | Una misma consulta autorizada protege listar, detallar, editar y descargar. Solo el propietario puede eliminar; la baja conserva el registro y sus relaciones. Los permisos revocados/inactivos no dan acceso. |
| S03: escalada de privilegios | Usuarios, roles, permisos, secciones y Django Admin exigen superadministrador con MFA. Staff no administra esas funciones. El registro público está cerrado. |
| S04: modificación de SMTP desde la web | La pantalla es de solo lectura y solo para superadministradores. Se eliminó la escritura de código/configuración y el envío de prueba desde la web. |
| S05: XSS | Los mensajes se escapan; el color del perfil se valida; los avatares se recodifican a PNG antes de servirlos. Se retiró el chatbot externo y el kit dinámico de iconos. |
| S07: operaciones por GET/CSRF | Las mutaciones requieren POST y CSRF. Se quitaron las rutas web de mantenimiento/cifrado. |
| S08: exposición en logs | Se quitaron impresiones de formularios/contraseñas, volcados de mantenimiento y contraseñas en el reporte de duplicados. El backend SMTP registra etapa/tipo/código, sin cuerpo ni credenciales. |
| S09: secretos históricos | Producción carga secretos del entorno, no de `settings.py`/`config.py`. Se agregó un comando de recifrado transaccional con simulación previa. **La rotación del servidor sigue siendo un paso de despliegue.** |
| S10: configuración insegura | `passing.production` exige secretos y hosts explícitos, desactiva DEBUG/toolbar, exige HTTPS y cookies seguras. No sirve `/media/` públicamente. **Nginx y permisos del servidor deben configurarse como se indica abajo.** |
| S11: generador débil | Se usa Web Crypto con selección uniforme de caracteres; no existe fallback a `Math.random`. |
| S12: dependencias vulnerables | Se actualizaron Django, cryptography, idna, Pillow, Selenium, sqlparse y urllib3. Se fijaron también las dependencias de MFA/QR. |

Además: límite persistente de intentos por IP/cuenta; reset por correo válido una hora;
respuestas privadas con `no-store`; adjuntos de hasta 10 MB y solicitudes de hasta
12 MB; cambio de correo con contraseña actual; prevención de autobaja en el flujo
de administración de usuarios. La sesión conserva las **24 horas absolutas desde el
ingreso** solicitadas: actividad y navegación no extienden ese plazo.

El propietario puede acceder a sus credenciales. Otros usuarios, incluidos los
superadministradores, necesitan permiso activo sobre una credencial no personal.
Un superadministrador puede gestionar permisos de credenciales compartibles; no
obtiene acceso automático a las personales. La recuperación de MFA sigue siendo
por otro superadministrador, con contraseña y OTP nuevos.

## Validación

```powershell
.\.venv\Scripts\python.exe manage.py test passbase.test_security login.test_mfa securitycontrol --settings=passing.test_settings --noinput
```

Las 42 pruebas pasaron. Los tests cubren rechazos con CSRF real, casos positivos de propietario/compartido,
revocación, staff, registro, XSS, adjuntos, límites, cifrado, recuperación y sesión.
Las pruebas de producción usan variables sintéticas y no envían correos.
`makemigrations --check --dry-run` no detectó cambios de modelos pendientes.

Se consultaron los metadatos de vulnerabilidades de PyPI para los **32 paquetes
resueltos** después de las actualizaciones: sin avisos publicados para esas versiones
al momento de la consulta. El resultado no equivale a ausencia de vulnerabilidades
desconocidas ni cubre el sistema operativo o todos los paquetes JavaScript.
El ejecutable `pip-audit` falló por OpenSSL en este Python de Windows; se usó HTTPS
nativo de Windows contra la API oficial de PyPI, sin desactivar validación TLS.

Referencias: [Django 5.2.17](https://docs.djangoproject.com/en/5.2/releases/5.2.17/),
[API JSON de PyPI](https://docs.pypi.org/api/json/).

## Despliegue en Ubuntu

1. Identificar el servicio y el entorno efectivos. En la salida compartida aparecían
   dos grupos de Gunicorn sobre el mismo socket. Revisar con `ps -eo user,pid,args`
   y `systemctl status <PID>`; dejar un solo servicio responsable del socket.
   Usar siempre `/home/Passing/env/bin/python`, sin paquetes de `~/.local`.
   Configurar `PYTHONNOUSERSITE=1` en el servicio.
2. Detener los workers identificados y respaldar la base, `media/`, configuración y
   claves actuales en almacenamiento privado. Verificar que el respaldo se pueda
   restaurar. No borrar las claves necesarias para leer respaldos históricos.
3. Instalar `requirements.txt` en el entorno del servicio. El nuevo perfil usa
   SQLite por defecto: `DJANGO_DB_PATH` debe apuntar a la **base existente**. Si el
   servidor usa PostgreSQL, adaptar `DATABASES` antes de arrancar; no iniciar por
   accidente una base SQLite vacía.
4. Configurar las variables de `production.env.example` mediante un archivo privado
   de systemd (`EnvironmentFile`, propietario root, modo 600). No subir ese archivo
   a Git ni servirlo por Nginx. `DJANGO_SECRET_KEY` debe ser nuevo y aleatorio;
   `CRYPTOGRAPHY_KEY` inicialmente debe ser la **clave actual de la bóveda**, en
   base64, sin el envoltorio Python `b'...'`. Rotar las credenciales SMTP/reCAPTCHA
   expuestas en el historial desde sus proveedores.
5. Con ese mismo entorno cargado, ejecutar:

```bash
/home/Passing/env/bin/python -m pip install -r requirements.txt
/home/Passing/env/bin/python manage.py migrate --settings=passing.production --noinput
/home/Passing/env/bin/python manage.py check --deploy --settings=passing.production
/home/Passing/env/bin/python manage.py collectstatic --settings=passing.production --noinput
```

**Sí, este cambio requiere `migrate`:** crea `securitycontrol_ratelimitbucket` y
aplica las migraciones de OTP/MFA si todavía no existen. No ejecutar `makemigrations`
en producción para este cambio. El archivo de entorno lo carga systemd para el
servicio; una terminal administrativa debe cargar explícitamente las mismas
variables antes de ejecutar los comandos anteriores.

El check de producción conserva dos advertencias deliberadas: HSTS no se aplica a
todos los subdominios y no solicita preload. Activarlos requiere verificar primero
que todo el dominio pueda exigir HTTPS; el sitio principal sí utiliza HSTS.

6. Configurar HTTPS en Nginx. Con Gunicorn accesible **solo por socket Unix** y
   Nginx como único proxy, usar `DJANGO_TRUST_PROXY_HTTPS=1` y
   `DJANGO_TRUSTED_PROXY_IPS=unix`. Nginx debe sobrescribir los encabezados, no
   reutilizar valores enviados por el navegador:

```nginx
client_max_body_size 12m;

location ^~ /media/ {
    return 404;
}

location /static/ {
    alias /home/Passing/static-collected/;
}

location / {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_pass http://unix:/home/Passing/passing.sock;
}
```

Integrar estos bloques en el servidor HTTPS existente; no duplicar bloques
`location`. Para proxy TCP local usar la IP real del peer, por ejemplo `127.0.0.1`,
en vez de `unix`, y bloquear acceso directo de Internet a Gunicorn. Si hay otro
proxy/CDN, configurar primero la cadena de confianza. Sin IP de cliente confiable,
los límites se compartirán entre los clientes que tengan la misma dirección vista
por Django. Agregar también límites en Nginx para evitar llegar al proceso Python.

7. Corregir el directorio `/home/Passing` que se mostró con modo 0777. Si el servicio
   continúa siendo `ubuntu:ubuntu`, conservar ese propietario y quitar escritura a
   grupo/otros: `sudo chmod go-w /home/Passing`. Verificar cada directorio padre con
   `namei -l /home/Passing/db.sqlite3` y `namei -l /home/Passing/media`.
   Base, backups y archivos privados solo deben ser legibles por el servicio y los
   operadores autorizados. Nginx solo necesita leer `static-collected/` y acceder al
   socket, no a `media/` ni a la base. No ejecutar `chmod -R 777` ni cambiar permisos
   recursivamente sin revisar qué archivos incluyen.
8. Arrancar el servicio con `DJANGO_SETTINGS_MODULE=passing.production`. Comprobar
   login + OTP, creación/edición propia, acceso compartido, rechazo ajeno, descargas,
   reset por correo y recuperación de MFA por otro superadministrador.
   El cambio de `SECRET_KEY` invalida sesiones y enlaces de reset anteriores, pero
   no cambia contraseñas de usuarios ni sus dispositivos OTP registrados.

### Logs y mantenimiento

Producción escribe logs estructurados a stderr, capturados por systemd/journald:
`journalctl -u <servicio-real> -f`. No depende de que Gunicorn pueda crear un
archivo de debug compartido entre workers. No habilitar DEBUG ni `smtplib` wire
debug en producción. Revisar/retirar los volcados históricos que contengan secretos
y su acceso en backups; el código nuevo no elimina registros históricos del servidor.

Programar diariamente, con el mismo entorno del servicio:

```bash
/home/Passing/env/bin/python manage.py clearsessions --settings=passing.production
/home/Passing/env/bin/python manage.py clear_security_buckets --settings=passing.production
```

### Rotación de la clave de la bóveda

No alcanza con reemplazar `CRYPTOGRAPHY_KEY`: hay que recifrar **credenciales e
historial**. Hacerlo con el servicio detenido y un backup verificado.

1. Mantener `CRYPTOGRAPHY_KEY` con el valor actual y preparar una nueva clave Fernet
   en `PASSING_NEW_CRYPTOGRAPHY_KEY`, dentro de un entorno privado. No escribir claves
   literales en argumentos de comandos ni guardarlas en el historial del shell.
2. Simular (no guarda cambios):

```bash
/home/Passing/env/bin/python manage.py rotate_vault_key --settings=passing.production
```

3. Si verifica todos los registros, aplicar:

```bash
/home/Passing/env/bin/python manage.py rotate_vault_key --settings=passing.production --apply --backup-confirmed
```

4. Solo después de completarse, configurar el servicio con la clave nueva como
   `CRYPTOGRAPHY_KEY`, quitar la variable temporal y reiniciar. El comando no cambia
   archivos de configuración. Si un registro está corrupto o tiene un formato
   histórico desconocido, aborta y revierte toda la transacción: investigar ese
   registro offline antes de continuar. No volver al código viejo con la base
   recifrada y una clave anterior; para rollback restaurar base y clave compatibles.

El recifrado también elimina los hashes heredados de contraseñas del campo `hash`.
Los respaldos antiguos siguen necesitando su clave antigua y deben quedar aislados.
Si se expusieron conjuntamente una base y su clave, recifrar no revoca las claves de
los servicios guardados: esas contraseñas deben cambiarse también en sus servicios.

## Límites del trabajo

Quedan sujetos a la revisión del servidor: firewall, Nginx, TLS, permisos reales,
rotación/revocación de secretos, backups, cuotas/antimalware de adjuntos y versiones
del sistema operativo. Los secretos TOTP y sesiones siguen usando el almacenamiento
de las librerías; los respaldos de la base deben estar cifrados y protegidos. No se
implementó cifrado de campo adicional para TOTP ni una auditoría integral de todos
los paquetes JavaScript. La CSP agregada es una defensa básica, no una política de
scripts estricta, porque la interfaz todavía utiliza scripts inline.
