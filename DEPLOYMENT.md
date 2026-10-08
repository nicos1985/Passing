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
DOCMANAGER_WEBHOOK_TOKEN=<valor aleatorio si se habilitan webhooks de Drive>
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<servidor SMTP>
DEFAULT_FROM_EMAIL=<remitente>
```

`DJANGO_TRUST_PROXY_HTTPS=1` solo es correcto si el proxy sobrescribe
`X-Forwarded-Proto` y el servidor de aplicación no recibe conexiones directas.
Configurar SMTP, webhook Bitrix24 y demás integraciones únicamente si se habilitan
sus funciones. `RECAPTCHA_TESTING=1` impide el arranque de producción.

## Esquema y arranque

1. Crear el esquema público con `python manage.py migrate_schemas --shared`.
2. Crear el tenant `public` y los tenants/dominios necesarios mediante un comando
   o migración de datos revisada; luego aplicar `python manage.py migrate_schemas`
   para los esquemas tenant. No usar `manage.py migrate` en este proyecto.
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
