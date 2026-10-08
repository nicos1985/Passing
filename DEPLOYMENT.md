# Passing: preparación de un servidor nuevo

Este procedimiento instala el código en una base PostgreSQL **vacía**. La conversión
de los datos de la instalación antigua (`login.CustomUser` a `accounts.CustomUser`,
permisos y credenciales Fernet) requiere un procedimiento separado, ensayado con una
copia restaurada de producción. No ejecutar `migrate_schemas` sobre la base antigua.

## Antes de instalar

- Crear un release Git que incluya `passing/settings.py`, las migraciones de todas
  las apps y el módulo `monitoring`. El archivo `.env` y las claves quedan fuera
  de Git. Verificar con `git status --short` que no falte ningún archivo requerido.
- Usar Python 3.12 y PostgreSQL 14 o posterior; crear una base vacía y un rol
  dedicado sin privilegios de superusuario. Restringir la conexión de PostgreSQL
  al servidor de aplicación y conservar copias privadas verificadas de la base,
  `media/`, `SECRET_KEY` y `CRYPTOGRAPHY_KEY`.
- Configurar HTTPS y los dominios del hub y los tenants en DNS y Nginx antes de
  habilitar el tráfico. No servir `media/` directamente: los adjuntos de la bóveda
  requieren autorización por registro.

## Entorno de la aplicación

Instalar las dependencias fijadas en `requirements.txt` en un entorno virtual
aislado. El servicio web, el worker de monitoreo y su watchdog deben leer el mismo
archivo de entorno privado, propiedad del usuario del servicio y modo `0600`.
Definir, como mínimo:

```text
DJANGO_DEBUG=0
SECRET_KEY=<clave aleatoria nueva, al menos 50 caracteres>
CRYPTOGRAPHY_KEY=<misma clave Fernet que usará la conversión de la bóveda>
ALLOWED_HOSTS=hub.example.com,empresa.example.com
HUB_ORIGIN=https://hub.example.com
BROKER_BASE_URL=https://hub.example.com
TENANT_BASE_URL=empresa.example.com
TENANT_SCHEME=https
CSRF_TRUSTED_ORIGINS=https://hub.example.com,https://empresa.example.com
DJANGO_TRUST_PROXY_HTTPS=1
DJANGO_HSTS_SECONDS=3600
DATABASE_NAME=passing
DATABASE_USER=passing_app
DATABASE_PASSWORD=<secreto privado>
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
RECAPTCHA_TESTING=0
RECAPTCHA_PUBLIC_KEY=<clave pública>
RECAPTCHA_PRIVATE_KEY=<clave privada>
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<servidor SMTP>
DEFAULT_FROM_EMAIL=<remitente>
```

`DJANGO_TRUST_PROXY_HTTPS=1` solo es correcto si el proxy sobrescribe
`X-Forwarded-Proto` y el servidor de aplicación no recibe conexiones directas.
Configurar SMTP y webhook Bitrix24 únicamente si se habilitan sus funciones.
La integración con Google Drive y el registro web de nuevos tenants están
deshabilitados en esta versión. El primer tenant se crea de forma controlada
durante la instalación; no se necesitan credenciales ni worker de Drive.
`RECAPTCHA_TESTING=1` impide el arranque de producción.

## Esquema y arranque

1. Crear el esquema público con `python manage.py migrate_schemas --shared`.
2. Crear el tenant `public` y los tenants/dominios necesarios mediante un comando
   o migración de datos revisada; luego aplicar `python manage.py migrate_schemas`
   para los esquemas tenant. No usar `manage.py migrate` en este proyecto.
   Crear el primer administrador únicamente desde la consola:

   ```bash
   python manage.py createsuperuser
   python manage.py link_tenant_superuser <schema_del_tenant> <username>
   ```

   El segundo comando crea la membresía y actualiza el vínculo con el tenant.
   No recibe la contraseña como argumento. El alta web de superusuarios no existe.
3. Ejecutar `python manage.py makemigrations --check --dry-run`,
   `python manage.py check --deploy` y `python manage.py collectstatic --noinput`
   con el mismo entorno que usarán los servicios. Revisar las advertencias de HSTS
   opcionales según la política de dominios; no activar preload sin verificarla.
4. Iniciar Gunicorn con `passing.wsgi:application` detrás de Nginx. Iniciar una
   sola instancia de `run_monitoring` y el timer `check_monitoring_worker` según
   `monitoring/README.md`. Si se habilita gestión documental asíncrona, configurar
   y verificar aparte su broker y worker Celery.
5. Verificar login y 2FA, acceso y denegación a credenciales y adjuntos, correo,
   Bitrix24, checks y latido del worker. Probar restauración y vuelta atrás antes
   de cambiar el tráfico de producción.

El corte de producción se define después de medir la conversión completa sobre un
backup restaurado y comparar usuarios, secciones, contraseñas, permisos, auditoría
y archivos. Mantener el servidor viejo sin nuevas escrituras hasta terminar la
validación del nuevo.

## Migración de la base existente: secuencia de ejecución

La migración de datos todavía necesita un importador para el esquema antiguo. Esta
secuencia define el ensayo y los controles; **no conectar la aplicación nueva a la
base antigua ni hacer el corte hasta que el importador y la reconciliación pasen**.

1. **Congelar una referencia.** En el servidor viejo, guardar el commit desplegado,
   versión de PostgreSQL, configuración de servicios y dominio. Verificar que la
   clave `CRYPTOGRAPHY_KEY` de `/etc/passing.env` se conserva en un gestor de
   secretos; no incluirla en SQL, Git, correo ni logs. Registrar los conteos de
   `passing_audit_counts.sql` y el estado de las cinco cuentas TOTP confirmadas.
2. **Backup privado y prueba de restauración.** Con el rol de PostgreSQL, que en
   este servidor es `postgres` (no `ubuntu`), generar un dump custom:

   ```bash
   sudo install -d -m 0700 -o postgres -g postgres /var/backups/passing
   sudo -u postgres pg_dump -Fc -d passing \
     -f /var/backups/passing/passing_antes_de_migrar.dump
   sudo -u postgres pg_restore -l \
     /var/backups/passing/passing_antes_de_migrar.dump >/dev/null
   ```

   Copiarlo por un canal cifrado al entorno de ensayo, con permisos `0600`.
   Restaurarlo en una base **aislada** de la base destino, por ejemplo
   `passing_legacy_stage`, y comprobar las cuentas y las 474 credenciales allí.
   La prueba real de backup incluye abrir esa base restaurada y leer sus tablas.
3. **Destino vacío.** En el servidor nuevo, crear `passing_new_stage`, cargar el
   release y ejecutar `migrate_schemas --shared` y `migrate_schemas` sobre esa base
   vacía. Crear el tenant y dominio controladamente. El código nuevo debe usar una
   copia segura de la clave Fernet antigua durante la importación; si se cambia la
   clave antes, las 474 credenciales dejan de descifrarse. Rotarla es una tarea
   posterior, con procedimiento y backup propios.
4. **Importar en orden de dependencias.** El importador deberá mapear IDs antiguos
   a nuevos para usuarios, membresía, secciones, roles y asignaciones, credenciales,
   permisos y adjuntos. Conservar los 21 usuarios, incluso los inactivos, para
   mantener referencias de propietarios; después aplicar las reglas de acceso de
   los siete activos. Importar los cinco secretos TOTP confirmados mediante canal
   privado y comprobar el acceso. No copiar `LogData.password` ni textos de logs
   con credenciales: generar auditoría nueva redactada o archivar el historial viejo
   en un depósito privado fuera de la nueva aplicación.
5. **Normalizar Fernet sin texto plano persistente.** Los 474 valores de `usuario`
   y 474 de `contraseña` son cadenas históricas de la forma `b'gAAAA...'`. El
   importador debe extraer el token de esa representación, verificarlo con la clave
   antigua, y escribir un token textual válido en destino. No llamar a
   `Contrasena.save()` con el token importado, porque el guardado de un registro
   nuevo cifra texto plano. Usar una importación controlada por lotes y comparar
   solo conteos e identificadores, nunca imprimir secretos. Recalcular el campo
   `hash` con `credential_fingerprint()` usando los valores descifrados en memoria;
   no conservar el SHA-256 antiguo, que permite ataques de diccionario.
6. **Resolver anomalías antes del corte.** La auditoría detectó un usuario cuyo rol
   directo no coincide con su rol intermedio, tres usuarios con varias filas
   `UserRoles` y 14 sin fila intermedia. Definir para cada uno el rol efectivo
   esperado y aprobar la tabla de correspondencias. Hay 172 logs con referencia a
   credenciales ausentes: no reconstruir contraseñas desde ellos. Verificar los 22
   adjuntos y probar autorización de descarga en el destino.
7. **Reconciliar el ensayo.** Exigir 21 usuarios, 474 credenciales, 29 secciones,
   17 roles, 817 asignaciones credencial por rol y 3371 permisos individuales,
   salvo diferencias explícitas y documentadas. Exigir 474/474 pares descifrables
   sin doble capa, cinco TOTP confirmados, cero propietarios personales vacíos,
   cero permisos apuntando a credenciales o usuarios inexistentes y 22 adjuntos
   accesibles solo a sus autorizados. Probar login, 2FA obligatorio/opcional,
   lectura y edición de credenciales, revocación, monitoreo y correo.
8. **Corte con ventana de un día.** Detener escrituras y workers del servidor viejo,
   generar un último dump, repetir la importación ensayada en un destino nuevo y
   repetir la reconciliación. Cambiar DNS/proxy solo cuando pase. Conservar el
   servidor viejo aislado y listo para volver atrás; si falla la verificación,
   devolver el tráfico al viejo **antes de reanudar escrituras en ambos**.

El informe de ensayo debe incluir duración, conteos de origen/destino, anomalías
resueltas, pruebas de 2FA y adjuntos, y pasos exactos de reversión. El CI debe
quedar verde antes de desplegar; `pip-audit` y Bandit ahora son bloqueantes.
