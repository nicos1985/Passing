# Passing — Gestor de contraseñas multi-tenant

Proyecto Django multi-tenant para gestión de contraseñas, permisos y notificaciones.

Resumen rápido
- Multi-tenant (django-tenants) con separación por schema.
- Usuarios y autenticación centralizada en `accounts` y `login`.
- Almacenamiento cifrado de credenciales en `passbase` (Fernet).
- Gestión de permisos y roles en `permission`.
- Flujo de solicitudes y notificaciones en `notifications`.

Documentación por app
- `accounts`: [accounts/DOCUMENTATION.md](accounts/DOCUMENTATION.md)
- `login`: [login/DOCUMENTATION.md](login/DOCUMENTATION.md)
- `passbase`: [passbase/DOCUMENTATION.md](passbase/DOCUMENTATION.md)
- `permission`: [permission/DOCUMENTATION.md](permission/DOCUMENTATION.md)
- `notifications`: [notifications/DOCUMENTATION.md](notifications/DOCUMENTATION.md)

Diagramas ER (Mermaid)
- `passbase/ER_RELATIONSHIP.md`
- `permission/ER_RELATIONSHIP.md`
- `notifications/ER_RELATIONSHIP.md`

Instalación y ejecución (desarrollo)
1. Crear/activar entorno virtual:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Migraciones y creación de tenant (si aplica):

```bash
python manage.py migrate
# Cree y configure tenants según su flujo con django-tenants
```

Ejecutar tests

```bash
python manage.py test
```

Puntos de seguridad importantes
- Configure `CRYPTOGRAPHY_KEY` en `settings` antes de poner en producción.
- Evitar ejecutar `passbase/management/commands/delete_tenants.py` fuera de entornos controlados.
- `passbase/scraping.py` es experimental y no está pensado para producción.

Notas para desarrolladores
- Los archivos `DOCUMENTATION.md` por app contienen detalles de modelos, vistas, y flujos.
- Para consolidar la documentación en un sitio estático recomiendo MkDocs o Sphinx.

Contacto
- Para cambiar la estructura de docs o generar un sitio estático dímelo y lo preparo.
