# Revisión de seguridad de Passing — 17/09/2026

> **Estado histórico:** este informe describe el código antes de las correcciones.
> Ver [correcciones y despliegue](security-hardening.md) para el estado actual.
> Los tests ahora son regresiones: `OK` significa que los controles verificados pasaron.

## Resultado y alcance

**Hay fallas confirmadas de autorización que permiten acceder a credenciales ajenas
aun con el 2FA correctamente verificado. Conviene corregirlas antes de desplegar.**

Revisión del código local de autenticación/2FA, sesiones, usuarios, permisos, bóveda,
adjuntos, notificaciones, SMTP, plantillas, cifrado, dependencias y configuración.
Se ejecutaron 11 reproducciones sobre una base de tests en memoria; todas confirmaron
el comportamiento inseguro descrito. No se modificó la base local de uso manual ni
producción, no se enviaron correos y se interceptó la escritura del archivo SMTP.
La revisión no aplicó correcciones funcionales: agregó este informe y las pruebas.

Los tests usan usuarios ficticios con sesión y OTP válidos. Esto representa un
usuario legítimo o malicioso ya autenticado; no simula romper el algoritmo TOTP.
Se dejó activo CSRF en el cliente de pruebas para comprobar cuáles rutas lo omiten.

No hubo acceso al Ubuntu de producción, Nginx, firewall, backups ni configuración
efectiva de Gunicorn. Los hallazgos de código son reproducibles localmente; los
riesgos que dependen del despliegue se distinguen debajo.

## Hallazgos prioritarios

### S01 — Crítico: lectura y modificación de credenciales ajenas mediante POST

- **Código:** `passbase/views.py:207`, control solo en `get()` en línea 218;
  `dispatch()` exento de CSRF en línea 231; carga sin filtro en `get_object()`
  línea 261. `templates/update-cont.html:53` incluye el secreto descifrado.
- **Precondición:** cuenta común con sesión y OTP verificados, sin permiso sobre
  la credencial solicitada.
- **Reproducción:** GET al formulario fue rechazado, pero POST vacío devolvió
  HTTP 200 con usuario y contraseña descifrados de otra cuenta. Un POST completo
  cambió esa contraseña. Ambas solicitudes carecían de token CSRF.
- **Impacto:** compromiso de confidencialidad e integridad de la bóveda mediante
  IDs de registros, incluidos los marcados como personales.
- **Corrección:** filtrar `get_queryset()`/`get_object()` por los permisos del
  usuario antes de leer, descifrar, auditar o modificar el registro. Aplicar el
  mismo control a GET y POST y quitar `csrf_exempt`. Responder 404/403 sin contexto
  del registro ajeno. Definir por separado quién puede leer y quién puede editar.
- **Pruebas:** `test_01`, `test_02`.

El registro público (`login/views.py:30`, `login/urls.py:17`) crea usuarios activos
sin aprobación. Se confirmó con reCAPTCHA simulado como válido (`test_09`): el captcha
es un control contra bots, no una aprobación administrativa. Si la aplicación es
interna, conviene usar invitaciones o aprobación. En combinación con S01 permite
que alguien se registre, configure su propio autenticador y ataque la bóveda.

### S02 — Alto: descarga y eliminación sin permiso sobre el registro

- **Código:** `passbase/views.py:314` (`ContrasDeleteView`) y `:524`
  (`DescargarArchivo`), sin filtrado por propietario o permiso.
- **Reproducción:** una cuenta sin permiso descargó el contenido de un adjunto
  privado. También pudo enviar un POST válido con su propio CSRF a eliminar una
  credencial ajena, dejándola inactiva y eliminando los permisos asociados.
- **Detalle adicional:** el borrado llama primero a `DeleteView.form_valid()`
  (borrado físico/cascadas) y luego intenta guardar el objeto como inactivo. Esto
  no implementa un borrado lógico seguro y provoca pérdida de relaciones.
- **Corrección:** reutilizar la política de acceso por objeto, distinguir permiso
  de lectura/borrado y realizar un borrado lógico explícito y transaccional si esa
  es la intención. Servir adjuntos únicamente mediante la ruta autorizada; revisar
  también si Nginx permite descargarlos directamente desde `/media/`.
- **Pruebas:** `test_03`, `test_10`.

### S03 — Alto: un staff puede convertirse en superadministrador

- **Código:** `login/views.py:150`, `UserUpdateView`; `login/forms.py`, `UserForm.Meta`.
- **Reproducción:** una cuenta `is_staff=True`, `is_superuser=False` envió su propio
  formulario con `is_superuser=on` y quedó como superadministrador.
- **Causa:** la vista admite staff y el formulario permite modificar los campos
  `is_superuser`, `is_staff` e `is_active` sin comprobar quién realiza el cambio.
- **Impacto:** acceso a administración total y a recuperación de autenticadores de
  otras cuentas. El atacante sigue pudiendo usar su propio OTP para esa recuperación.
- **Corrección:** reservar cambios de privilegios a superadministradores, impedir
  la autopromoción y limitar qué cuentas/campos puede administrar un staff. No basta
  con ocultar controles en la plantilla.
- **Prueba:** `test_04`.

### S04 — Alto: cualquier usuario autenticado puede reconfigurar SMTP

- **Código:** `passing/views.py:62`, especialmente la escritura en `:83`.
- **Reproducción:** una cuenta común escribió una nueva configuración SMTP. En el
  test se interceptaron `open()` y el diccionario de settings para no alterar ningún
  archivo real. También se confirmó que el password SMTP se imprime a stdout.
- **Impacto:** interrupción o desvío de correos futuros de recuperación cuando los
  procesos vuelvan a cargar la configuración modificada. La vista no actualiza
  `django.conf.settings` de todos los workers, por lo que el efecto puede requerir
  reinicio/recarga; no se afirma que cambie inmediatamente todos los envíos.
- **Corrección:** quitar esta configuración de la interfaz o restringirla a
  superadministradores con reautenticación. No escribir credenciales en código
  Python ni imprimirlas; usar variables de entorno o un almacén de secretos.
- **Prueba:** `test_05`.

### S05 — Alto: HTML almacenado se inserta sin escapar en páginas administrativas

- **Código:** `templates/base.html:167` (`message|safe`), `permission/views.py:125`
  y otros mensajes construidos con nombres/comentarios provenientes de usuarios.
- **Reproducción:** un nombre de credencial con una etiqueta HTML y un manejador
  de evento llegó sin escapar al HTML que recibe un staff al conceder acceso.
  Se usó un marcador inocuo (`void(0)`), sin extraer datos ni ejecutar acciones.
- **Impacto:** XSS almacenado: un nombre controlado por otro usuario puede ejecutar
  JavaScript con el origen de Passing cuando la acción administrativa muestra el
  mensaje. Esto permite leer respuestas y realizar acciones con esa sesión.
- **Corrección:** eliminar `|safe` para mensajes que contienen datos variables;
  cuando sea necesario HTML, construirlo con `format_html()` y argumentos escapados.
  Revisar todos los mensajes, no solo la ruta reproducida.
- **Prueba:** `test_07`.

### S06 — Alto: permisos inactivos siguen permitiendo leer secretos

- **Código:** `passbase/views.py:45` filtra `perm_active=True` en la lista;
  `:74`, `:95`, `:220` comprueban solo `permission=True` en detalle/edición.
- **Reproducción:** con `permission=True, perm_active=False`, la credencial no
  apareció en la lista, pero la URL directa del detalle mostró su contraseña.
- **Corrección:** centralizar la política de autorización y exigir todos los
  estados relevantes en cada ruta, incluida la actividad de la credencial.
- **Prueba:** `test_06`.

### S07 — Alto: acciones de permisos aceptan GET y evitan la protección CSRF

- **Código:** `permission/views.py:92` (`grant_permission`), `:273` (`delete_rol`),
  `:288` (`update_owner`); `passbase/views.py:539` (`denypermission`);
  `login/views.py:215` (`activate_user`).
- **Reproducción:** un GET sin CSRF concedió acceso a una credencial, usando una
  sesión staff. Django no aplica la comprobación CSRF a GET.
- **Impacto:** un enlace o navegación puede ejecutar una operación con la sesión
  de un administrador. `SameSite=Lax` no impide toda navegación GET entre sitios.
- **Corrección:** usar POST + CSRF para mutaciones, responder 405 a GET y validar
  que los IDs del usuario, la credencial y la notificación correspondan realmente
  a la solicitud autorizada. Las tareas de mantenimiento masivo deben salir de URLs.
- **Prueba:** `test_08` (concesión de permisos); las otras rutas se revisaron en código.

### S08 — Alto: contraseñas en texto claro en logs y salidas de diagnóstico

- **Código:** `passbase/views.py:135`, `:147`, `:678`; `passing/views.py:98`;
  `permission/views.py:427` y el informe de contraseñas repetidas.
- **Reproducción:** al crear una credencial se imprimió su contraseña sin cifrar.
  La prueba de SMTP también capturó la contraseña del servidor de correo.
- **Impacto:** quien acceda a stdout de Gunicorn, journald, logs o copias puede
  obtener secretos sin descifrar la base. `remake_pass` también escribe secretos
  descifrados en `log_pass.txt` si se ejecuta esa ruta.
- **Corrección:** retirar prints de datos de formularios, secretos e informes que
  contengan valores reales; registrar solo IDs, acciones y resultados. Revisar
  retención y accesos de logs existentes y rotar credenciales según la exposición.
- **Pruebas:** `test_11`, `test_05`; tareas de mantenimiento no se ejecutaron.

### S09 — Alto: secretos presentes en el historial de Git

- **Código:** `passing/settings.py:31` y `:34`; historial de ese archivo.
- **Confirmación:** la `SECRET_KEY` del archivo local coincide con la guardada en
  commits históricos, por ejemplo `4e29aa29`. Se compararon valores sin imprimirlos.
  También aparece una clave histórica de cifrado; no coincide con la clave actual
  local. No se confirmó que estas claves sean las efectivas de producción.
- **Impacto:** excluir el archivo hoy con `.gitignore` no elimina secretos ya
  registrados. Acceso al repositorio/historial puede comprometer firmas y, con la
  clave de cifrado correspondiente, respaldos antiguos de la bóveda.
- **Corrección:** verificar qué claves usa producción, moverlas fuera del código
  y planificar su rotación. **No reemplazar `CRYPTOGRAPHY_KEY` directamente:** primero
  hace falta un respaldo y un proceso de recifrado/verificación de todos los datos
  e históricos. Rotar `SECRET_KEY` es otra operación; puede invalidar sesiones y
  tokens. Limpiar el historial no sustituye la rotación de claves expuestas.

## Configuración, dependencias y otros riesgos

### S10 — Alto si se reproduce en producción: configuración y permisos del servidor

`check --deploy --settings=passing.settings` reportó seis advertencias locales:
`DEBUG=True`, clave Django de desarrollo, falta de HSTS y redirección HTTPS,
cookies de sesión/CSRF sin `Secure`. Además, `ALLOWED_HOSTS=['*']` aparece en el
archivo local. Es necesario contrastarlo con el settings real de Ubuntu y Nginx;
no se considera comprobado en producción solo por existir localmente.

La salida de Ubuntu compartida en esta conversación sí mostró `/home/Passing`
con `drwxrwxrwx` (0777). Eso permite escribir en la carpeta a otros usuarios locales;
debe corregirse la propiedad/grupo y retirar la escritura global, preservando el
acceso necesario de Gunicorn/Nginx. No se ejecutaron cambios remotos.

Verificar TLS, hosts permitidos, cookies `Secure`, `DEBUG=False`, ausencia de debug
toolbar en producción, límites de uploads y que Nginx no publique repositorio,
base, logs, configuración ni adjuntos privados. En el traceback compartido antes,
Django se cargaba desde `/home/ubuntu/.local/...`; confirmar que Gunicorn usa el
entorno y las versiones esperadas.

### S11 — Medio: el generador de contraseñas usa Math.random()

`templates/create-cont.html:158`, `templates/update-cont.html:115` y una plantilla
alternativa usan `Math.random()`, que no es un generador criptográfico. Reemplazarlo
por `crypto.getRandomValues()` con selección sin sesgo o generar en el servidor con
`secrets`. No se intentó predecir contraseñas existentes; es un hallazgo de código.

### S12 — Dependencias con parches de seguridad pendientes

`requirements.txt` fija Django **5.2.8**, también instalado en el entorno probado.
Las notas oficiales documentan correcciones posteriores; 5.2.17 fue publicado el
4 de agosto de 2026. Actualizar dentro de la rama 5.2 mantenida y ejecutar pruebas
de compatibilidad. No se atribuye automáticamente a Passing cada CVE: varias
requieren componentes que esta aplicación no utiliza (por ejemplo GeoDjango).

- [Django 5.2.9: correcciones posteriores a 5.2.8](https://docs.djangoproject.com/en/5.2/releases/5.2.9/).
- [Django 5.2.13: incluye corrección de denegación de servicio en multipart](https://www.djangoproject.com/weblog/2026/apr/07/security-releases/).
- [Django 5.2.17: parche publicado](https://docs.djangoproject.com/en/5.2/releases/5.2.17/).

La aplicación acepta archivos, por lo que revisar el parser multipart y los límites
de tamaño es relevante. No se enviaron cargas de denegación de servicio. La consulta
de avisos no reemplaza un análisis completo de todas las dependencias transitivas.

Otros puntos para el siguiente endurecimiento:

- Límites de intentos por cuenta/IP en contraseña, registro y reset por correo;
  el throttling TOTP existente no cubre esas operaciones. Los límites del proxy
  de producción no se pudieron revisar.
- `Cache-Control: no-store` en respuestas de la bóveda y descargas privadas;
  actualmente las pantallas de MFA sí usan `never_cache`, las de secretos no.
- Secretos TOTP en base de datos sin cifrado de campo, y claves temporales del
  alta en sesiones: proteger respaldos y considerar cifrado con clave separada.
- Archivos subidos: tamaño, tipo, cuota y almacenamiento privado. No se confirmó
  la configuración de publicación de `/media/` en Nginx.
- Reducir scripts externos en páginas que contienen contraseñas descifradas;
  revisar CSP e integridad de dependencias frontend. No se hizo un escaneo completo
  de los paquetes JavaScript copiados en `static/`.
- Una sesión de 24 horas, solicitada por el usuario, mantiene la ventana de abuso
  si se roba la cookie. No es por sí sola un fallo de implementación.

## Orden sugerido de corrección

1. Bloquear S01–S04 y revisar la política de registro público. Centralizar permisos
   y proteger rutas administrativas en el servidor.
2. Corregir XSS, CSRF, permisos inactivos y eliminación; convertir las reproducciones
   en tests que exijan rechazo y ausencia de datos ajenos.
3. Eliminar filtraciones en logs, revisar secretos históricos y planificar rotación.
4. Actualizar Django/dependencias y verificar configuración, archivos y permisos de Ubuntu.
5. Endurecer límites, caché, generación de contraseñas y almacenamiento de secretos.

## Reproducción y límites

```powershell
.\.venv\Scripts\python.exe manage.py test docs.security_probes --settings=passing.test_settings --noinput -v 2
```

`docs.security_probes` ahora importa las pruebas de regresión de `passbase.test_security`.
Las reproducciones originales fueron invertidas al corregir los problemas.

Las pruebas usan una base en memoria y archivos en memoria. No se hizo un pentest
contra el servidor público ni una auditoría de infraestructura, y no se puede
afirmar ausencia de otras vulnerabilidades.
