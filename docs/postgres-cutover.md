# Separar Passing del superusuario PostgreSQL

Estado comprobado el 22/09/2026: Passing se conecta como `postgres` a la base
`postgres` del cluster PostgreSQL 14 (`localhost:5432`). `rolsuper=t` confirma
que la aplicación usa un superusuario. Las 19 tablas listadas en el esquema
`public` corresponden a Django y Passing. No se inspeccionaron otros esquemas,
extensiones, el tamaño de la base ni el usuario de otras conexiones. Este plan
prepara una nueva base `passing` y un rol `passing_app` sin superusuario; **no se
ejecutó en Ubuntu**.

## Comprobaciones previas (solo lectura)

```bash
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1 -c \
  "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' ORDER BY 1;"
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_size_pretty(pg_database_size('postgres')) AS database_size;"
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1 -c \
  "SELECT datname FROM pg_database WHERE datname = 'passing';"
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1 -c \
  "SELECT rolname FROM pg_roles WHERE rolname = 'passing_app';"
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1 -c \
  "SELECT usename, application_name, client_addr, state FROM pg_stat_activity WHERE datname = 'postgres' AND pid <> pg_backend_pid();"
```

Debe haber espacio para el archivo de backup y la nueva base, además del margen
normal de PostgreSQL. Detener el proceso duplicado descrito en
`security-hardening.md` antes del cambio. Si `passing` o `passing_app` ya existen,
no reutilizarlos sin inspección; los comandos de creación fallan sin borrar nada.
Identificar cualquier otro proceso capaz de escribir en `postgres` y pausarlo
durante el dump y la comprobación de los conteos.

## Copia y cambio durante mantenimiento

1. Cerrar escrituras a Passing y detener **las dos** unidades Gunicorn que sigan
   activas. La página mostrará una interrupción hasta terminar el cambio. No
   detener PostgreSQL ni Nginx. Confirmar con `systemctl is-active` y `ss`.
2. Crear un directorio privado para el backup y obtener un dump completo de la
   base actual. Guardar aparte una copia privada de `media/` y de las claves de
   cifrado necesarias para leer ese respaldo.

```bash
sudo systemctl stop gunicorn.service live.service
sudo install -d -o postgres -g postgres -m 700 /var/backups/passing
sudo -u postgres pg_dump -p 5432 -Fc -d postgres \
  -f /var/backups/passing/postgres-before-passing-cutover.dump
sudo chmod 600 /var/backups/passing/postgres-before-passing-cutover.dump
sudo -u postgres pg_restore -l \
  /var/backups/passing/postgres-before-passing-cutover.dump > /dev/null
```

Si `pg_dump` o la lectura del archivo fallan, no avanzar. El backup contiene
contraseñas cifradas, sesiones y datos personales; conservarlo fuera de rutas web.

3. Crear un rol de login sin privilegios de cluster. En `psql`, `\password`
   solicita la nueva contraseña sin guardarla en el historial en texto plano.
   No pasar contraseñas literales como argumento de `psql`, ni pegarlas en el chat.

```bash
sudo -u postgres psql -p 5432 -d postgres -X -v ON_ERROR_STOP=1
```

Dentro de `psql`:

```sql
CREATE ROLE passing_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password passing_app
\q
```

4. Crear una base vacía en el **mismo cluster 14** y restaurar el dump como
   `passing_app`. `--no-owner` evita devolver la propiedad al rol `postgres`;
   `--no-acl` evita copiar permisos antiguos. `--single-transaction` revierte
   todo el contenido restaurado si ocurre un error.

```bash
sudo -u postgres createdb -p 5432 -O passing_app -T template0 passing
sudo -u postgres pg_restore -p 5432 -d passing --role=passing_app \
  --no-owner --no-acl --single-transaction \
  /var/backups/passing/postgres-before-passing-cutover.dump
sudo -u postgres psql -p 5432 -d passing -X -v ON_ERROR_STOP=1 -c \
  'REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE, CREATE ON SCHEMA public TO passing_app;'
```

Si falla la restauración, conservar la base original intacta; investigar el error
antes de continuar. No usar `--clean` ni restaurar sobre la base `postgres`.

5. Comprobar conteos en **ambas** bases, propiedad de tablas y conexión con la
   contraseña nueva. La comparación se hace antes de ejecutar migraciones, que
   crearán tablas nuevas en el destino.

```bash
for db in postgres passing; do
  sudo -u postgres psql -p 5432 -d "$db" -X -v ON_ERROR_STOP=1 -c \
    'SELECT (SELECT count(*) FROM login_customuser) AS users, (SELECT count(*) FROM passbase_contrasena) AS credentials, (SELECT count(*) FROM permission_contrapermission) AS grants, (SELECT count(*) FROM passbase_logdata) AS audit_rows;'
done
sudo -u postgres psql -p 5432 -d passing -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_get_userbyid(c.relowner) AS owner, count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S','v','m') GROUP BY 1;"
psql -h localhost -p 5432 -U passing_app -d passing -W -X -c \
  'SELECT current_user, current_database();'
```

Todos los objetos de Passing restaurados deben pertenecer a `passing_app` y los
conteos originales deben coincidir. Si hay otros esquemas o extensiones, revisar
sus permisos antes de conectar la aplicación.

6. En el archivo privado de entorno del servicio configurar:

```text
DJANGO_DB_ENGINE=django.db.backends.postgresql
DJANGO_DB_NAME=passing
DJANGO_DB_USER=passing_app
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=5432
DJANGO_DB_PASSWORD=<contraseña del nuevo rol, solo en el archivo privado>
```

Con el **mismo entorno** que usará Gunicorn, ejecutar `migrate`, `check --deploy`
y `collectstatic` del paso 5 de `security-hardening.md`. Arrancar solo
`gunicorn.service` y comprobar login+OTP, credenciales, permisos, adjuntos y
reset de contraseña a través de Nginx antes de reabrir el tráfico normal.

## Vuelta atrás

La base original `postgres` permanece sin modificación por este procedimiento.
Si una comprobación falla **antes** de admitir nuevos cambios de usuarios, detener
Gunicorn, restaurar el archivo de entorno anterior (motor, base, usuario y clave)
y arrancar `gunicorn.service`. Confirmar de nuevo el login. Si la nueva base ya
recibió escrituras, volver sin reconciliar esos cambios perdería datos; detener
el tráfico y planificar la recuperación antes de cambiar la conexión.

Conservar el backup, la base original y sus claves según la política de retención
hasta verificar la nueva base y el procedimiento de restauración. Eliminar después
el acceso del servicio al superusuario `postgres` y rotar esa contraseña cuando
ninguna aplicación la utilice; no borrar el rol administrativo del cluster.

Referencias oficiales: [roles y atributos](https://www.postgresql.org/docs/14/role-attributes.html),
[`pg_dump`](https://www.postgresql.org/docs/14/app-pgdump.html),
[`pg_restore`](https://www.postgresql.org/docs/14/app-pgrestore.html),
[`psql \password`](https://www.postgresql.org/docs/14/app-psql.html).
