"""Short, user-facing guides for the tenant's main navigation modules."""

HELP_TOPICS = {
    "inicio": {
        "title": "Conocer Passing",
        "eyebrow": "Guía general",
        "lead": "Passing reúne el trabajo cotidiano de seguridad y soporte en un mismo lugar. Inicio resume lo que requiere atención y te lleva a cada módulo según tus permisos.",
        "icon": "fa-house",
        "landing": "home_tenant",
        "features": [
            ("Prioridades", "Consultá los indicadores y pendientes visibles para tu rol: tratamientos, evaluaciones y novedades."),
            ("Navegación", "El menú agrupa las funciones por módulo. Si no ves una opción, pedí a un administrador que revise tu rol."),
            ("Avisos y perfil", "La campanita concentra avisos; en Mi perfil podés revisar tus datos y elegir las notificaciones de Telegram."),
        ],
        "steps": [
            "Revisá las tarjetas de Inicio y abrí el pendiente que corresponda.",
            "Trabajá en el módulo donde se registra la acción y dejá su estado actualizado.",
            "Volvé a Inicio para comprobar qué quedó pendiente o consultá los avisos recibidos.",
        ],
        "tips": [
            "Los módulos comparten usuarios y permisos, pero cada uno conserva sus propios registros y flujos.",
            "La ayuda explica la operación general; las acciones disponibles dependen del rol que tengas asignado.",
        ],
    },
    "contrasenas": {
        "title": "Contraseñas",
        "eyebrow": "Bóveda",
        "lead": "Guardá credenciales en secciones, consultá los accesos autorizados y compartilos mediante permisos o solicitudes sin exponer las claves en listados.",
        "icon": "fa-key",
        "landing": "listpass",
        "features": [
            ("Bóveda y secciones", "Buscá una credencial por nombre o sección y abrí su detalle para consultar sus datos y adjuntos."),
            ("Accesos", "Las credenciales pueden ser personales o compartidas. Los roles y permisos individuales determinan quién puede usarlas."),
            ("Solicitudes", "Cuando alguien necesita una clave compartida, puede solicitar acceso; los responsables reciben el pedido y deciden si autorizarlo."),
            ("Rotación", "La fecha de actualización ayuda a seguir cuándo conviene revisar o reemplazar una credencial."),
        ],
        "steps": [
            "Creá una sección o elegí una existente y registrá la credencial con un nombre reconocible.",
            "Asigná el acceso a los roles o usuarios que corresponda; evitá permisos más amplios de lo necesario.",
            "Ante una solicitud, revisá el motivo, autorizá si corresponde y registrá la rotación cuando cambie la clave.",
        ],
        "tips": [
            "La lista no muestra las claves directamente: abrí el detalle o usá la acción de copia cuando tengas acceso.",
            "No pongas secretos en el nombre, descripción o enlace de una credencial.",
        ],
    },
    "recursos": {
        "title": "Recursos",
        "eyebrow": "Inventario y terceros",
        "lead": "Organizá activos de información, proveedores, proyectos y clientes para saber qué existe, quién es responsable y qué seguimiento necesita.",
        "icon": "fa-server",
        "landing": "informationassets-list",
        "features": [
            ("Activos", "Registrá su categoría, estado, clasificación de información y dueño. El detalle reúne los datos de cada activo."),
            ("Proveedores", "Mantené el registro de terceros y sus evaluaciones; las plantillas de checklist ayudan a repetir el mismo criterio."),
            ("Proyectos y clientes", "Relacioná el trabajo con sus proyectos y organizaciones correspondientes."),
            ("Préstamos", "Cuando un activo cambia de manos, registrá la entrega, devolución y trazabilidad del movimiento."),
        ],
        "steps": [
            "Da de alta el recurso y asignale un responsable y una clasificación adecuada.",
            "Abrí el detalle para completar la información y registrar evaluaciones o movimientos aplicables.",
            "Revisá periódicamente registros desactualizados y cambios de estado.",
        ],
        "tips": [
            "La calidad del inventario mejora los análisis de riesgo: mantené dueño, estado y clasificación al día.",
            "Los permisos pueden habilitar lectura, creación, edición y eliminación por separado.",
        ],
    },
    "riesgos": {
        "title": "Riesgos",
        "eyebrow": "Evaluación y tratamiento",
        "lead": "Identificá amenazas y vulnerabilidades, evaluá su impacto y probabilidad, y seguí las acciones para reducir o aceptar el riesgo.",
        "icon": "fa-triangle-exclamation",
        "landing": "evaluation-list",
        "features": [
            ("Catálogos", "Amenazas y vulnerabilidades describen qué puede ocurrir y por qué un recurso podría verse afectado."),
            ("Evaluaciones", "Relacionan el objeto evaluado con sus factores de riesgo y dejan registrado el nivel resultante."),
            ("Tratamientos", "Documentan la respuesta, el responsable, la fecha y el avance de las acciones."),
            ("Asistente", "Ayuda a priorizar seguimientos y redactar recordatorios; las decisiones siguen en manos del equipo."),
        ],
        "steps": [
            "Elegí el activo, proveedor u objeto a evaluar y revisá las amenazas y vulnerabilidades relevantes.",
            "Completá la evaluación y confirmá los datos antes de darla por finalizada.",
            "Definí un tratamiento, asigná responsable y fecha, y actualizá su etapa hasta el cierre.",
        ],
        "tips": [
            "Una evaluación en borrador no representa una decisión final.",
            "Registrá evidencia de las acciones y revisá los riesgos cuando cambie el contexto.",
        ],
    },
    "inteligencia": {
        "title": "Inteligencia de amenazas",
        "eyebrow": "Señales externas",
        "lead": "Reuní información de fuentes configuradas, revisá resultados relevantes y decidí si corresponde incorporarlos al análisis de riesgos.",
        "icon": "fa-brain",
        "landing": "threat_intel:run-list",
        "features": [
            ("Fuentes y ejecuciones", "Las fuentes definen de dónde llega la información; cada ejecución muestra cuándo se consultó y qué obtuvo."),
            ("Elementos y análisis IA", "Revisá el contenido relevante y usá el análisis como apoyo para clasificarlo, sin sustituir la validación humana."),
            ("Revisiones y reportes", "Documentá decisiones, prepará reportes y vinculá hallazgos con amenazas cuando aporten contexto."),
        ],
        "steps": [
            "Comprobá que las fuentes necesarias estén configuradas y revisá la última ejecución.",
            "Abrí los elementos relevantes, verificá contexto y descartá falsos positivos.",
            "Registrá la revisión y, si afecta a la empresa, relacioná el hallazgo con Riesgos o generá un reporte.",
        ],
        "tips": [
            "Una mención externa no equivale por sí sola a una vulnerabilidad propia.",
            "El análisis automático facilita el trabajo, pero necesita revisión antes de tomar decisiones.",
        ],
    },
    "monitorizacion": {
        "title": "Monitorización",
        "eyebrow": "Salud de servicios",
        "lead": "Comprobá disponibilidad y tiempos de respuesta, detectá incidentes y seguí su atención desde una sola ubicación.",
        "icon": "fa-heart-pulse",
        "landing": "monitoring:dashboard",
        "features": [
            ("Monitores", "Configurá ping, HTTP, TCP, TLS o heartbeat. En HTTP podés definir códigos esperados, latencia máxima y una condición JSON."),
            ("Tablero", "Cada barra resume un check reciente: verde OK, amarillo lento, rojo falla y gris sin dato."),
            ("Incidentes", "Cuando se alcanza el umbral de fallas o lentitud se abre un incidente; su recuperación y su gestión en Bitrix24 son eventos distintos."),
            ("Contexto", "Usá el detalle, los históricos, los mantenimientos y las marcas de despliegue para investigar cambios."),
        ],
        "steps": [
            "Creá el monitor, elegí el tipo y configurá destino, intervalo, reglas y destinatarios.",
            "Observá los primeros checks y ajustá umbrales para que representen el comportamiento esperado.",
            "Ante una alerta, abrí el incidente, revisá el detalle y seguí la recuperación; programá mantenimientos antes de trabajos previstos.",
        ],
        "tips": [
            "Los checks se realizan desde el servidor de Passing, no desde el navegador del usuario.",
            "La página Información explica cada estado, código HTTP y error técnico con más detalle.",
        ],
        "reference": ("Interpretar estados y errores", "monitoring:information"),
    },
    "soporte": {
        "title": "Central de soporte",
        "eyebrow": "Avisos de Bitrix24",
        "lead": "Concentrá los avisos de chats de soporte de varios portales Bitrix24 y notificá a las personas de guardia por Telegram.",
        "icon": "fa-headset",
        "landing": "supporthub:inbox",
        "features": [
            ("Portales y grupos", "Vinculá cada portal y seleccioná los chats o grupos que querés vigilar."),
            ("Bandeja", "Consultá actividad, cantidad de mensajes y estado de entrega. Abrí el enlace para responder directamente en Bitrix24."),
            ("Guardias", "Asigná turnos con horario de Argentina para distribuir avisos según quién esté disponible."),
            ("Telegram", "El bot se configura en Configuración general y cada usuario vincula su chat y sus suscripciones desde Mi perfil."),
        ],
        "steps": [
            "Configurá el portal y el grupo que recibirá consultas; verificá que el worker de soporte esté activo.",
            "Designá personas y turnos de guardia, y pediles que vinculen Telegram en su perfil.",
            "Revisá la bandeja; si falla una entrega, examiná el estado y reintentá cuando corresponda.",
        ],
        "tips": [
            "La notificación avisa de actividad y enlaza al chat; las respuestas se hacen en Bitrix24.",
            "Passing guarda el seguimiento del aviso, no el contenido completo de la conversación.",
        ],
    },
    "configuracion": {
        "title": "Configuración",
        "eyebrow": "Administración",
        "lead": "Administrá usuarios, roles, parámetros del espacio y canales de notificación desde un único lugar.",
        "icon": "fa-gear",
        "landing": "config",
        "features": [
            ("Usuarios", "Creá usuarios, revisá su estado y asignales el acceso que necesitan para trabajar."),
            ("Roles y permisos", "Definí qué módulos puede leer, crear, editar o eliminar cada rol; los permisos de contraseñas tienen su propia gestión."),
            ("Configuración general", "Ajustá políticas del espacio, incluido el segundo factor, y las integraciones disponibles."),
            ("Notificaciones", "Configurá los canales generales; cada persona elige sus suscripciones de Telegram en Mi perfil."),
        ],
        "steps": [
            "Revisá las políticas del espacio y los canales de notificación antes de incorporar usuarios.",
            "Creá o ajustá roles con los permisos mínimos necesarios y asigná usuarios a cada uno.",
            "Probá el acceso con una cuenta común y revisá periódicamente usuarios y permisos activos.",
        ],
        "tips": [
            "La obligación de usar 2FA se define a nivel del espacio; cada usuario completa su enrolamiento al ingresar.",
            "Las credenciales SMTP permanecen en la configuración del servidor y no se muestran en estas pantallas.",
        ],
    },
}

HELP_ORDER = ("inicio", "contrasenas", "recursos", "riesgos", "inteligencia", "monitorizacion", "soporte", "configuracion")
