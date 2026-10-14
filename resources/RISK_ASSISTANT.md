# Asistente de riesgos

El análisis corre una vez al día por tenant, después de las 09:00 de Argentina, dentro del servicio `run_supporthub`. También puede iniciarse de forma manual con `python manage.py run_risk_assistant`. Una segunda ejecución del mismo día no duplica sugerencias ni avisos.

Para probarlo con casos sintéticos en `empresa1`:

```bash
python manage.py seed_risk_assistant_demo --tenant empresa1
python manage.py run_risk_assistant --tenant empresa1 --force --rules-only
```

La primera orden carga cinco evaluaciones marcadas `[RA-DEMO]` y se puede repetir sin duplicarlas. La segunda vuelve a analizar el día aunque el worker ya haya hecho un ciclo; `--rules-only` evita llamadas externas durante la prueba. Deberían aparecer cuatro sugerencias en `/resources/assistant/`. Para probar el texto redactado por IA, repetir la segunda orden sin `--rules-only`, con `OPENAI_API_KEY` configurada. La IA podrá redactar el resumen aunque las sugerencias ya existan; la priorización de cada caso se consulta solo al crearlo.

Antes de iniciar el worker en una instalación nueva, aplicar las migraciones de tenants con `python manage.py migrate_schemas --tenant`. La bandeja está en **Riesgos → Asistente de riesgos**. Solo las personas con permiso de lectura de evaluaciones pueden verla; para revisar, posponer o descartar se requiere permiso de cambio. En **Mi perfil → Avisos por Telegram**, cada persona con acceso a riesgos puede activar el resumen diario.

Las reglas detectan reevaluaciones pendientes, tratamientos vencidos, riesgos altos sin revisión en 180 días y riesgos altos sin tratamiento. Las sugerencias son informativas: nunca cambian evaluaciones ni tratamientos automáticamente. El mismo caso se conserva hasta que cambie la evaluación o el tratamiento, y el estado de revisión queda registrado.

Si hay `OPENAI_API_KEY` y `RISK_ASSISTANT_AI_ENABLED` no es `false`, el servicio externo recibe por lotes únicamente referencias temporales como `R1`, categorías de regla, nivel de riesgo, antigüedad en días, días de vencimiento y etapa numérica. Para redactar el resumen diario recibe solo cantidades de sugerencias abiertas, prioridades y tipos. No se envían IDs de base, nombres, descripciones, URLs, IPs, correos ni datos de usuarios. Solo acepta del modelo una prioridad de una lista cerrada y una frase breve para el resumen; Passing calcula las cifras y tipos, y agrega el enlace localmente. Ante un fallo externo o una respuesta inválida, queda el texto local. Para operar sin IA externa, configurar `RISK_ASSISTANT_AI_ENABLED=false`.

Para proponer un próximo paso en cada sugerencia, Passing examina localmente las descripciones de la evaluación y de la vulnerabilidad. Solo extrae etiquetas de una lista fija (por ejemplo, control de acceso, autenticación, parches, respaldos o cifrado) y la familia de vulnerabilidad. El texto original no sale de Passing. La recomendación de IA se valida antes de guardarse; si falta o incluye enlaces o datos con formato sensible, se utiliza una recomendación local. El resumen diario incluye el próximo paso de una sugerencia abierta prioritaria, para facilitar la acción desde Telegram.

En Windows, la consulta de IA de este módulo se hace mediante PowerShell y HTTPS de Windows para evitar un conflicto local de Python/OpenSSL. La clave y el resumen abstracto pasan por entrada estándar al proceso; no se escriben en argumentos ni archivos temporales. En Linux se usa el cliente Python existente.

El resumen se envía una vez por día a quienes tengan activada la suscripción de riesgos en Telegram, siempre que existan sugerencias abiertas. Incluye pendientes anteriores aunque no haya sugerencias nuevas ese día. Repetir el análisis con `--force` actualiza el texto guardado, pero no reenvía una notificación que ya se haya entregado.

Para volver a recibir el texto actual sin esperar al día siguiente, ingresar a **Riesgos → Asistente de riesgos** y pulsar **Enviar prueba a mi Telegram**. El botón aparece solo para el usuario con chat vinculado, activo y suscripto a riesgos. La prueba usa exactamente el resumen guardado y el mismo enlace que el aviso diario; se envía únicamente al chat propio y admite un envío cada 30 segundos.
