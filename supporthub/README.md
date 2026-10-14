# Central de soporte Bitrix24

Passing reúne avisos de grupos de soporte de varios portales Bitrix24. La bandeja
`/support/` muestra portal, grupo, hora, cantidad de mensajes, estado de Telegram y
un enlace al chat. No guarda el texto, adjuntos ni nombres de participantes. Guarda
IDs de mensaje y autor para deduplicar; elimina el historial tras 90 días.

## Alcance de esta primera versión

- Se vigilan grupos (`chat123`) elegidos en la configuración. Los mensajes privados
  quedan fuera; requieren definir una cuenta de integración que participe de cada
  conversación o una integración diferente.
- El webhook de cada portal pertenece a una cuenta que integra esos grupos y tiene
  permiso `im`. Se cifra con `CRYPTOGRAPHY_KEY` de Passing.
- El worker consulta `im.v2.Event.subscribe` y `im.v2.Event.get` cada 20 segundos.
  Bitrix24 conserva eventos por 24 horas. Hay que mantener el worker en marcha y
  vigilar su última consulta en la pantalla de configuración.
- Para reducir ruido, se agrupan mensajes del mismo chat durante 60 segundos. Se
  ignoran el usuario del webhook, bots, mensajes de sistema y los IDs de soporte
  cargados en cada grupo. Telegram recibe solamente nombre de portal, grupo,
  cantidad, hora y enlace.
- Se programa una persona principal y una suplente para cada rango de fechas. Los
  formularios y las horas mostradas usan `America/Argentina/Buenos_Aires`, aunque
  el usuario esté en otro país. Si no hay turno, avisa a quienes tengan activado
  «respaldo sin turno». Los turnos son rangos concretos; todavía no se repiten
  automáticamente cada semana.
- Si falla el envío principal, se crea un intento para la suplente. Los envíos se
  reintentan con espera creciente hasta cinco veces. Los fallidos aparecen en la
  bandeja y un superusuario puede reintentarlos.

## Avisos personales

El bot configurado por el superusuario se comparte entre soporte, monitoreo y
solicitudes de acceso a contraseñas. Cada persona entra a **Mi perfil → Avisos por
Telegram**, vincula su chat privado mediante un código recibido allí y activa las
categorías deseadas. El código vence a los diez minutos y solo se guarda su hash.
Si el chat ya figura asignado a otro usuario de Passing, su dueño puede
recuperarlo desde su perfil confirmando el código recibido en ese mismo chat.
La transferencia desactiva las suscripciones anteriores y cancela los envíos
pendientes; luego hay que elegir las preferencias nuevas.
Los destinatarios existentes mantienen su suscripción a soporte; las categorías
nuevas requieren activación explícita. Soporte sigue respetando turnos y respaldo.
Monitoreo avisa incidentes y recuperaciones solo a quienes pueden administrar
monitores. Solicitudes de acceso se envían solo a superusuarios, sin el
nombre ni el contenido de la contraseña. El worker `run_supporthub` entrega las
tres categorías y reintenta fallas temporales. La cola guarda solo IDs, estado y
errores acotados, y se limpia a los 90 días.

La pantalla de soporte permite eliminar portales Bitrix24, grupos vigilados y
turnos de guardia con confirmación. Borrar un portal elimina sus grupos y el
historial asociado; borrar un grupo elimina sus avisos. Las cuentas de Telegram
se administran en Configuración general. Si una cuenta está asignada a un turno,
hay que eliminar primero ese turno para poder borrarla.

## Preparación

1. Aplicar las migraciones del tenant con el procedimiento de despliegue habitual:
   `python manage.py migrate_schemas`. Hacerlo primero sobre una base de ensayo.
2. Crear un bot con BotFather. En **Configuración general → Notificaciones**,
   guardar el token y usar **Comprobar bot**. Passing lo cifra con
   `CRYPTOGRAPHY_KEY`, no vuelve a mostrarlo y el worker lee los cambios sin
   reiniciar. Si todavía existe `SUPPORT_TELEGRAM_BOT_TOKEN` en el entorno,
   funciona como respaldo para instalaciones no migradas; el token guardado en
   Passing tiene prioridad. No guardar el token en el repositorio.
3. Pedir a cada persona de guardia que abra el bot en Telegram y le envíe `/start`.
   Pulsar **Buscar IDs de chats privados** en la misma pantalla y copiar el número
   correspondiente a cada destinatario. La consulta solo muestra ID, nombre y
   usuario de Telegram; no guarda ni presenta el contenido del mensaje. `getUpdates`
   requiere que ese bot no tenga otro webhook de Telegram activo.
4. En Bitrix24, crear un webhook entrante con permiso `im` para una cuenta que sea
   miembro de los grupos vigilados. Conviene una cuenta dedicada por portal. No
   usar la misma cuenta con otra aplicación que consuma `im.v2.Event.get`: el cursor
   confirma eventos para todas las aplicaciones de ese usuario.
5. En **Central de soporte → Configurar**, cargar cada portal y su webhook; luego
   los grupos, con `dialogId` como `chat123`. Pegar el enlace real a cada grupo
   desde Bitrix24. Si se omite el enlace, **Abrir** lleva al inicio del portal.
   Configurar los IDs de usuarios de soporte cuyos mensajes no deban generar
   avisos. Agregar cuentas Telegram en Configuración general, o pedir a cada
   persona que vincule su chat desde el perfil.
6. Programar los turnos, por ejemplo sábado 09:00 a lunes 09:00, siempre con
   horas de Argentina. Evitar huecos; agregar al menos un destinatario de respaldo
   sin turno. Los turnos superpuestos se rechazan.
7. Ejecutar un ciclo de prueba con `python manage.py run_supporthub --once`.
   Revisar el estado de cada portal en Configurar. Luego habilitar **una sola**
   instancia continua de `run_supporthub`. Hay un ejemplo en
   `systemd/passing-supporthub.service`; adaptar usuario y rutas al servidor.

## Prueba funcional por portal

Con el worker activo, enviar desde una persona distinta a la cuenta de integración
un mensaje de prueba en un grupo configurado. Esperar hasta unos 80 segundos por
la agrupación y el sondeo. Confirmar que aparece en la bandeja, que el enlace abre
el chat correcto y que llega un Telegram a la guardia. Repetir con una cuenta del
equipo incluida en «IDs a ignorar» y comprobar que no genera aviso.

La disponibilidad de `im.v2` y del permiso `im` debe comprobarse en cada portal.
Una falla de permisos o de plan se muestra junto al portal. Bitrix24 documenta que
`Event.get` exige suscripción previa, confirma eventos con `nextOffset` y permite
un solo consumidor por usuario.

## Seguridad y operación

Los webhooks y el token de Telegram se cifran en la base con la clave existente de
Passing. La variable de entorno del token sigue disponible como respaldo. La
configuración queda limitada a
superusuarios y la bandeja admite el permiso `supporthub.view_support_inbox`.
La integración solo hace solicitudes HTTPS a portales públicos configurados por el
superusuario; conviene restringir además la salida del servidor por firewall.
Verificar periódicamente la última consulta del portal y los avisos sin entregar.

Referencias de API:

- https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/im.v2/events/event-subscribe.html
- https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/im.v2/events/event-get.html
- https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/im.v2/events/events.html
- https://core.telegram.org/bots/api#sendmessage
- https://core.telegram.org/bots/api#getupdates
