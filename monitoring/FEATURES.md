# Nuevas funciones del módulo de monitorización

## Mantenimientos programados

En **Monitorización → Mantenimientos programados** se pueden crear ventanas únicas, diarias o semanales por monitor. La fecha inicial marca la primera repetición; la diferencia entre inicio y fin define la duración de una ventana recurrente, hasta 24 horas. Los horarios se ingresan en la zona horaria elegida en la pantalla. Por defecto se detecta la del navegador; se puede elegir Italia, Argentina o UTC. Cada ventana recurrente conserva su zona horaria para respetar sus cambios de horario de verano. Durante una ventana los checks y los incidentes siguen registrándose, pero no se generan entregas de apertura o recuperación por correo y Bitrix24. El mantenimiento rápido de una hora sigue disponible por separado.

## Heartbeat

Crear un monitor de tipo **Tarea programada**, indicar intervalo y margen en minutos y guardar. Se muestra un token una sola vez; almacenarlo como secreto en el proceso que se vigila. Al terminar correctamente, ese proceso debe hacer un POST a la dirección mostrada con el encabezado `X-Monitoring-Token`. No se envía ni almacena la salida de la tarea. La señal usa el dominio del tenant, nunca una URL pública compartida. Si el token se pierde, se puede regenerar desde el detalle; el anterior deja de servir.

Cuando pasa el intervalo más el margen sin señal, el worker abre un incidente. La siguiente señal correcta lo recupera. El worker debe seguir en ejecución para detectar ausencias; el endpoint de señal funciona independientemente del ciclo del worker. El token se almacena solo como SHA-256 y no se coloca en la URL.

## Despliegues

Desde el detalle de cada monitor se registra fecha, versión y nota. Las marcas aparecen como líneas violetas en el gráfico de latencia cuando caen dentro del período elegido. Al pasar el cursor o enfocarlas se ve la versión y la nota. Se pueden editar o eliminar. El servidor impide registros idénticos para el mismo monitor, fecha, versión y nota. Se retienen 365 días.

## Estado interno

`/monitoring/status/` muestra a cualquier usuario autenticado del tenant únicamente nombre, tipo y estado de cada monitor. No incluye destinos, detalles de checks, URLs, destinatarios, tokens ni enlaces de administración. Se actualiza cada 30 segundos. Los administradores también pueden abrirla desde el dashboard.

## Operación

Aplicar `monitoring.0012_schedules_heartbeats_deployments` en todos los tenants y reiniciar el proceso web y el worker para cargar el código nuevo. La creación de monitores heartbeat exige un worker activo para detectar las señales ausentes.
