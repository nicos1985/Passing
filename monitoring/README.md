# Monitorización en Passing

App Django por tenant para checks ping, HTTP/HTTPS, puertos TCP y certificados TLS, incidentes, correo y negociaciones de Bitrix24.

## Integración

`passing/settings.py` está excluido de Git en este proyecto. En cada instalación, agregar `"monitoring"` a `TENANT_APPS` después de `"docmanager"`. La ruta `/monitoring/` está registrada en `passing/urls_tenant.py` y el enlace aparece en el menú lateral del tenant para superusuarios o usuarios administradores con el permiso `monitoring.manage_monitoring`.

Ejecutar las migraciones de tenant con el comando habitual del proyecto (`migrate_schemas`). Asignar el permiso `manage_monitoring` a los administradores que usarán la consola. El servidor web no ejecuta checks; iniciar una sola instancia de `python manage.py run_monitoring` bajo `systemd`.

Los checks ping usan `ping` del sistema. Funcionan en Windows y Linux; el worker de producción está preparado para Linux. El usuario del servicio debe poder ejecutar `ping` sin privilegios adicionales. Comprobarlo desde la cuenta de servicio antes de iniciar el worker.

Los checks HTTP/HTTPS hacen un GET al endpoint indicado y no siguen redirecciones. Por defecto, las respuestas 200-299 son correctas; cada servicio puede configurar códigos o rangos aceptados (por ejemplo `200-299,301`), una latencia máxima y una comparación opcional de un valor JSON por ruta (`health.status` = `"ok"`). Cuando se comprueba JSON o una respuesta JSON falla, se leen como máximo 16 KiB del cuerpo. El resultado individual conserva únicamente un motivo genérico, la latencia y el código HTTP. El valor esperado se escribe como literal JSON (`"ok"`, `true`, `1` o `null`). Una respuesta JSON inválida, una ruta ausente, un valor diferente o un cuerpo mayor al límite cuentan como falla. Timeout, errores TLS y de conexión/DNS también se muestran con su motivo. La URL no admite credenciales, parámetros ni fragmentos; usar HTTPS directamente si HTTP redirige. Los requests verifican certificados TLS y no usan proxies ni credenciales del entorno.

Las rutas JSON usan puntos para navegar objetos y listas: `items.0.status` toma el primer elemento de `items`, y `0.status` toma el primer elemento cuando la respuesta empieza directamente con una lista. Los índices empiezan en cero.
El detalle del check distingue un cuerpo que no es JSON válido de una ruta JSON ausente. La pantalla `Información`, accesible desde el dashboard y el detalle, explica estados, códigos HTTP y causas frecuentes.

Al abrir un incidente HTTP, se guarda únicamente la primera muestra JSON disponible durante la falla. Antes de guardarla se limitan profundidad, cantidad de elementos y tamaño (4.000 caracteres), y se ocultan claves habituales de credenciales y contacto. Se cifra con Fernet usando una clave derivada de `SECRET_KEY`; cambiar esa clave sin migrar datos impide leer muestras previas. El texto solo se descifra en el detalle del incidente para usuarios con permiso `manage_monitoring`. No se agrega a correos ni negociaciones Bitrix24 y se elimina con el incidente según la retención habitual. La sanitización reduce el riesgo, pero un servicio puede incluir datos sensibles bajo nombres de campo no previstos; usar endpoints de salud con respuestas mínimas siempre que sea posible.

La latencia máxima opcional se configura en milisegundos para ping, HTTP, TCP y TLS. Una respuesta correcta que supera el umbral se registra como «respuesta lenta» en ámbar, con su latencia medida. Tras los checks consecutivos configurados se abre un incidente de lentitud, distinto de una caída; se notifica por correo, Bitrix24 y Telegram cuando esos canales están activos. Al volver debajo del umbral durante los checks correctos requeridos, el incidente se recupera. Si pasa de lento a falla real, se cierra el incidente anterior y se abre uno de caída. Los checks lentos cuentan como disponibles, pero siguen visibles durante 365 días y participan en promedio y p95.

El check TCP intenta abrir una conexión a `host:puerto` y mide el tiempo de conexión; no envía datos de aplicación. El check TLS acepta `host` o `host:puerto` (443 por defecto), verifica cadena y nombre con el almacén de confianza del sistema y alerta cuando faltan menos días para vencer que el umbral configurado (30 por defecto). En ambos tipos se admite IPv6 como `[dirección]:puerto`; no se guarda el certificado ni datos de la conexión.

## Bitrix24 y correo

Configurar `MONITORING_BITRIX_WEBHOOK_URL` en el entorno del worker con la URL base del webhook entrante, terminada en `/rest/<usuario>/<código>/`. Debe tener permiso CRM para leer y crear negociaciones en la categoría 174. El módulo usa la primera etapa disponible de ese embudo, deja la negociación abierta y busca por `originatorId`/`originId` antes de reintentar una creación cuyo resultado haya sido incierto. Bitrix24 puede exigir otros campos obligatorios configurados en esa cuenta; verificarlos con una prueba controlada.

En esta cuenta, la opción «MONITOR PASSING» (ID 7258) pertenece al campo «Cuenta» (`UF_CRM_1751302650`); se asigna al crear la negociación. El ID del incidente enlaza al detalle del negocio en el portal, construyendo la URL solo con el dominio del webhook para no exponer el token.

Al crear una negociación se completa el título y, si existe un campo personalizado de texto llamado «Asunto», también ese campo. El worker consulta la definición de campos del CRM para encontrar «Criticidad» y su opción «Crítica»; envía el ID real de esa opción. Si no encuentra el campo o la opción, deja la entrega pendiente con un error visible en el incidente para evitar crear una gestión sin criticidad. Las negociaciones ya creadas no se modifican retroactivamente.

El worker consulta cada cinco minutos si las negociaciones asociadas están cerradas. El incidente muestra «No reconocido», «Reconocido» o «Resuelto» según la acción local y el cierre en Bitrix24. La recuperación técnica del servicio se muestra por separado; Passing no cambia etapas ni cierra negociaciones en Bitrix24. Si una negociación se reabre, el estado vuelve al reconocimiento local. Se guarda solo el estado de cierre, la hora de consulta y un error seguro si la consulta falla.

El correo reutiliza `EMAIL_*` y `DEFAULT_FROM_EMAIL` del proyecto. Los destinatarios se configuran en cada monitoreo, separados por comas.

No registrar la URL del webhook: contiene un secreto. Asegurar el archivo de entorno del servicio con permisos del usuario de ejecución.

## Operación

- Intervalo inicial: 60 segundos por destino.
- Umbral inicial: 3 fallos para abrir incidente, 2 éxitos para recuperarlo.
- `python manage.py run_monitoring --once` ejecuta un ciclo para diagnóstico.
- La compactación corre una vez al día dentro del worker. Los OK individuales se conservan 7 días; respuestas lentas, fallas, incidentes y resúmenes horarios, 365 días.
- Los nuevos resúmenes horarios guardan un histograma pequeño de latencias OK para estimar p95. Los resúmenes creados antes de esta versión conservan suma y cantidad, pero no permiten reconstruir el percentil; la pantalla indica la cobertura del p95 cuando es parcial.
- El worker guarda un latido al terminar cada ciclo de cada tenant. El dashboard muestra el último ciclo y los checks atrasados (más de 2 minutos o un intervalo de retraso). Considera detenido al worker después de 3 minutos sin latido.
- `python manage.py check_monitoring_worker` es un watchdog independiente del worker. El timer de `systemd` lo ejecuta cada minuto: si hay monitoreos activos y el latido falta o hay checks atrasados, envía una alerta a `MONITORING_WORKER_ALERT_EMAILS` y crea una negociación Bitrix24 si está configurado `MONITORING_BITRIX_WEBHOOK_URL`. Cada canal se reintenta en el siguiente ciclo si falla; una búsqueda por origen evita duplicar negociaciones. La alerta se rearma cuando vuelve a estar sano. Se registra solo el estado mínimo de entrega y el ID de la negociación.
- El dashboard consulta `/monitoring/live/` cada 1,5 segundos para estado actual, checks recientes e incidentes. También consulta `/monitoring/history/` cada 5 segundos y muestra 60 segmentos por servicio, uno por minuto de la última hora: verde para OK, ámbar para respuesta lenta, rojo para falla o error del monitor y gris si no hubo medición. El porcentaje se calcula sobre los checks realmente ejecutados. Al pasar el mouse por un segmento se ve hora, resultado y latencia. El encabezado distingue la conexión de la vista del latido del worker. Ambos endpoints exigen el mismo permiso que la consola y no se cachean.
- Cada monitoreo puede detenerse e iniciarse desde su fila. Detener pausa los checks futuros sin borrar el historial; iniciar programa el próximo check de inmediato. Los monitoreos archivados antes de este cambio aparecen detenidos y se pueden iniciar.
- La papelera abre una confirmación antes de eliminar un monitoreo. El borrado definitivo elimina sus checks, resúmenes, incidentes y entregas pendientes; no elimina negociaciones que ya existan en Bitrix24.
- El nombre del servicio abre su detalle con configuración, incidentes, los 60 minutos de salud y latencias por check para 1, 6 o 24 horas o 7 días. El detalle se actualiza cada 15 segundos. El dashboard muestra solo los 10 checks globales más recientes.
- En el detalle también se puede ver disponibilidad por 24 horas, 7, 30 o 365 días. La disponibilidad es `(OK + lentos) / (OK + lentos + fallas)`; los errores locales de ejecución se muestran aparte. Las barras agregan por hora, día o semana; se combinan los checks recientes con los resúmenes horarios. La latencia promedio y el p95 estimado usan checks OK y lentos con latencia. Se indica cantidad y duración de incidentes dentro del período, incluyendo los que siguen abiertos. La vista histórica se actualiza cada minuto.
- Cada incidente muestra el estado de las entregas de correo y Bitrix24, cantidad de intentos, próximo reintento y un error seguro y legible. Permite adelantar un reintento pendiente o agotado. La prueba de conexión SMTP solo autentica; la de Bitrix24 solo consulta campos del CRM. El correo de prueba se envía únicamente al correo del administrador o a un destinatario configurado en ese monitoreo, cuando el administrador lo solicita.
- La tarjeta del dashboard muestra caídas y respuestas lentas activas. El enlace «Historial de incidentes» muestra también los recuperados y las gestiones resueltas; permite buscar por monitor, filtrar por estado y abrir cada detalle. Los incidentes se conservan hasta la retención de 365 días, salvo que se elimine su monitor.
- Se usa un advisory lock de PostgreSQL para impedir dos workers activos a la vez.

## Despliegue con systemd

Adaptar las rutas y usuario de `systemd/passing-monitoring.service`, copiarlo a `/etc/systemd/system/`, ejecutar `systemctl daemon-reload` y habilitar el servicio. La instancia web de Passing y el worker deben usar las mismas variables de base de datos; el worker además necesita el webhook Bitrix24.

Copiar también `systemd/passing-monitoring-watchdog.service` y `systemd/passing-monitoring-watchdog.timer`, adaptar las mismas rutas y usuario, y habilitar el timer con `systemctl enable --now passing-monitoring-watchdog.timer`. Configurar en `/etc/passing/monitoring.env` `MONITORING_WORKER_ALERT_EMAILS=admin@empresa.com,otro@empresa.com` y el webhook Bitrix24 existente. Si no se configura un canal, el watchdog solo informa por los canales disponibles. Revisar su ejecución con `systemctl list-timers passing-monitoring-watchdog.timer` y `journalctl -u passing-monitoring-watchdog.service`. Este timer detecta problemas del worker mientras el servidor y la base de datos siguen disponibles; para detectar la caída completa del servidor se necesita una comprobación desde otro equipo.
