# Ruta: backend/app/logs/recomendaciones.py
# Motor de recomendaciones de ciberseguridad y buenas prácticas de negocio:
# analiza el texto de cada línea de log ya generada por el sistema y devuelve
# una severidad y una sugerencia concreta de qué hacer y dónde hacerlo. No
# está atado a ningún rubro de negocio específico: usa términos genéricos
# aplicables a cualquier sistema de administración.

import re
from collections import OrderedDict

# --- Reglas de detección ---
# Cada regla tiene: un identificador único, el patrón de texto a buscar
# (insensible a mayúsculas), en qué categorías de log aplica, la severidad
# (baja, media, alta, critica) y la recomendación mostrada al administrador.
# El orden importa: se evalúa de arriba hacia abajo y se usa la primera
# coincidencia.
REGLAS = [
    # --- Seguridad técnica ---
    {
        "id": "limite_peticiones",
        "patron": re.compile(r"l[ií]mite de peticiones excedido", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "alta",
        "titulo": "Exceso de peticiones (posible fuerza bruta o abuso de la API)",
        "recomendacion": (
            "Revisa la IP registrada en esta línea dentro de seguridad.log. "
            "Si se repite mucho desde la misma IP, bloquéala temporalmente en tu "
            "firewall o router. También puedes reducir el límite permitido en "
            "backend/app/utils/limitador.py o en los decoradores @limitador.limit "
            "de los endpoints sensibles (ej. login)."
        ),
    },
    {
        "id": "clave_logs_invalida",
        "patron": re.compile(r"clave inv[aá]lida o ausente|ingreso al panel de logs", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "alta",
        "titulo": "Intento de acceso al panel de monitoreo con clave incorrecta",
        "recomendacion": (
            "Alguien con una cuenta de administrador intentó entrar al panel de "
            "logs sin la clave correcta. Si esto se repite, cambia el valor de "
            "CLAVE_ACCESO_LOGS en el archivo backend/.env, reinicia el servidor "
            "y revisa qué usuario administrador generó el intento."
        ),
    },
    {
        "id": "token_invalido",
        "patron": re.compile(r"token inv[aá]lido o expirado", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "media",
        "titulo": "Token de sesión inválido o expirado",
        "recomendacion": (
            "Puede ser una sesión vencida normal, o alguien probando tokens "
            "falsos. Si ves muchas repeticiones desde la misma IP en poco "
            "tiempo, es sospechoso: revisa esa IP y considera reducir "
            "ACCESS_TOKEN_EXPIRE_MINUTES en backend/.env."
        ),
    },
    {
        "id": "usuario_inactivo_con_token",
        "patron": re.compile(r"usuario no existe o est[aá] inactivo", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "media",
        "titulo": "Token usado para un usuario desactivado o inexistente",
        "recomendacion": (
            "Alguien sigue usando un token de una cuenta ya desactivada. Ve al "
            "módulo de Usuarios y confirma que esa cuenta esté realmente "
            "inactiva; si el problema persiste, cambia la SECRET_KEY en el "
            ".env para invalidar todos los tokens antiguos de una vez."
        ),
    },
    {
        "id": "acceso_sin_permisos",
        "patron": re.compile(r"acceso sin permisos suficientes", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "media",
        "titulo": "Intento de acceso a un recurso fuera del rol asignado",
        "recomendacion": (
            "Un usuario autenticado intentó entrar a una sección que no le "
            "corresponde según su rol. Revisa en el módulo de Usuarios si el "
            "rol asignado es el correcto; si el mismo usuario insiste varias "
            "veces, podría tratarse de un intento de escalar privilegios."
        ),
    },
    {
        "id": "sistema_bloqueado_suscripcion",
        "patron": re.compile(r"sistema bloqueado por suscripci[oó]n", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "baja",
        "titulo": "Uso del sistema mientras está bloqueado por pago vencido",
        "recomendacion": (
            "Esto es un aviso informativo, no un ataque. Una vez confirmado el "
            "pago, desbloquea el sistema desde la pantalla de bloqueo usando "
            "la CLAVE_MAESTRA_DESBLOQUEO definida en backend/.env."
        ),
    },
    {
        "id": "respuesta_401",
        "patron": re.compile(r"respuesta 401 en", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "media",
        "titulo": "Peticiones rechazadas por falta de autenticación",
        "recomendacion": (
            "Revisa si corresponde a un usuario legítimo con la sesión "
            "vencida o a un tercero probando acceder sin credenciales válidas. "
            "Si es lo segundo, considera bloquear la IP de origen."
        ),
    },
    {
        "id": "respuesta_403",
        "patron": re.compile(r"respuesta 403 en", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "media",
        "titulo": "Peticiones rechazadas por permisos insuficientes",
        "recomendacion": (
            "Revisa en el módulo de Usuarios qué cuenta generó estas "
            "peticiones y confirma que su rol sea el correcto para lo que "
            "está intentando hacer."
        ),
    },
    {
        "id": "respuesta_429",
        "patron": re.compile(r"respuesta 429 en", re.IGNORECASE),
        "categorias": {"seguridad"},
        "severidad": "alta",
        "titulo": "Bloqueo automático por exceso de peticiones",
        "recomendacion": (
            "El limitador de peticiones ya frenó esta IP automáticamente. Si "
            "ocurre seguido, considera bloquearla también a nivel de red y "
            "revisar si corresponde a un intento de fuerza bruta sobre login."
        ),
    },
    # --- Errores técnicos ---
    {
        "id": "error_integridad_bd",
        "patron": re.compile(r"integrityerror", re.IGNORECASE),
        "categorias": {"errores"},
        "severidad": "media",
        "titulo": "Error de integridad en la base de datos",
        "recomendacion": (
            "Probablemente se intentó guardar un dato duplicado (ej. un "
            "correo o nombre de usuario que ya existe) o falta una relación "
            "obligatoria. Revisa el formulario del frontend que originó la "
            "petición y agrega validaciones previas si hace falta."
        ),
    },
    {
        "id": "error_operacional_bd",
        "patron": re.compile(r"operationalerror", re.IGNORECASE),
        "categorias": {"errores"},
        "severidad": "alta",
        "titulo": "Error operacional de la base de datos",
        "recomendacion": (
            "El archivo de base de datos puede estar bloqueado por otro "
            "proceso, sin espacio en disco, o con permisos incorrectos. "
            "Verifica que ningún otro programa lo tenga abierto y que exista "
            "espacio disponible en el disco del servidor."
        ),
    },
    {
        "id": "error_jwt",
        "patron": re.compile(r"jwterror", re.IGNORECASE),
        "categorias": {"errores"},
        "severidad": "media",
        "titulo": "Error al procesar un token de sesión",
        "recomendacion": (
            "Puede deberse a que se cambió SECRET_KEY recientemente mientras "
            "había sesiones activas. Si el problema es constante, revisa que "
            "SECRET_KEY y ALGORITHM en backend/.env no se hayan modificado "
            "por error."
        ),
    },
    {
        "id": "error_permisos_archivo",
        "patron": re.compile(r"permissionerror", re.IGNORECASE),
        "categorias": {"errores"},
        "severidad": "alta",
        "titulo": "Error de permisos al leer o escribir un archivo",
        "recomendacion": (
            "El proceso del backend no tiene permisos suficientes sobre una "
            "carpeta (por ejemplo, la de imágenes o la de logs). Verifica los "
            "permisos del sistema operativo sobre esas carpetas."
        ),
    },
    {
        "id": "error_archivo_no_encontrado",
        "patron": re.compile(r"filenotfounderror", re.IGNORECASE),
        "categorias": {"errores"},
        "severidad": "baja",
        "titulo": "Archivo esperado no encontrado",
        "recomendacion": (
            "Revisa que la ruta configurada en el .env exista realmente y que "
            "no se haya movido o eliminado manualmente algún archivo."
        ),
    },
    # --- Acciones sensibles de negocio (genéricas, sin depender de un rubro) ---
    {
        "id": "precio_modificado",
        "patron": re.compile(r"modific[oó] el precio", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "media",
        "titulo": "Modificación de precio de un producto",
        "recomendacion": (
            "Confirma que el cambio de precio haya sido autorizado. Si no "
            "reconoces esta modificación, contacta al usuario indicado en "
            "esta línea y, de ser necesario, revierte el precio desde el "
            "módulo de Inventario."
        ),
    },
    {
        "id": "venta_eliminada",
        "patron": re.compile(r"elimin[oó] una venta|elimin[oó] el registro de venta", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "alta",
        "titulo": "Eliminación de un registro de venta",
        "recomendacion": (
            "Eliminar ventas puede afectar tus reportes financieros. Verifica "
            "en el módulo de Reportes que los totales cuadren y confirma con "
            "el usuario responsable el motivo de la eliminación."
        ),
    },
    {
        "id": "devolucion_registrada",
        "patron": re.compile(r"registr[oó] una devoluci[oó]n|devoluci[oó]n de producto", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "media",
        "titulo": "Devolución registrada",
        "recomendacion": (
            "Verifica que la devolución tenga un motivo válido y que el "
            "inventario se haya actualizado correctamente en el módulo de "
            "Inventario."
        ),
    },
    {
        "id": "caja_abierta",
        "patron": re.compile(r"abri[oó] la caja|apertura de caja", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "baja",
        "titulo": "Apertura de caja registrada",
        "recomendacion": (
            "Esto es un evento normal de operación diaria. Verifica que el "
            "monto inicial registrado coincida con el efectivo real contado "
            "al abrir caja."
        ),
    },
    {
        "id": "caja_cerrada",
        "patron": re.compile(r"cerr[oó] la caja|cierre de caja", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "baja",
        "titulo": "Cierre de caja registrado",
        "recomendacion": (
            "Compara el monto final registrado contra el efectivo real "
            "contado al cerrar caja, y revisa el reporte de ventas del día en "
            "el módulo de Reportes para confirmar que coincidan."
        ),
    },
    {
        "id": "usuario_creado_o_editado",
        "patron": re.compile(r"cre[oó] un usuario|edit[oó] un usuario|cambi[oó] el rol de un usuario", re.IGNORECASE),
        "categorias": {"negocio"},
        "severidad": "media",
        "titulo": "Cambio en cuentas de usuario del sistema",
        "recomendacion": (
            "Confirma que la creación, edición o cambio de rol haya sido "
            "autorizada por el administrador principal. Revisa el módulo de "
            "Usuarios para validar que los roles asignados sean correctos."
        ),
    },
]

# Recomendación genérica cuando un error no coincide con ninguna regla específica
_RECOMENDACION_GENERICA_ERRORES = (
    "Revisa el mensaje completo y la ruta (endpoint) donde ocurrió este error "
    "dentro de errores.log. Si se repite seguido, considera agregar un manejo "
    "de excepción específico en ese endpoint dentro del backend."
)

# Recomendación genérica cuando una acción de negocio no coincide con ninguna regla
_RECOMENDACION_GENERICA_NEGOCIO = (
    "Revisa el detalle completo de esta acción en negocio.log y confirma que "
    "haya sido realizada por el usuario correcto y con la autorización "
    "correspondiente."
)


def analizar_mensaje(categoria: str, mensaje: str) -> tuple[str | None, str | None, str | None]:
    """
    Compara un mensaje de log contra las reglas conocidas y devuelve
    (identificador_regla, severidad, recomendacion). Si no coincide con
    ninguna regla, devuelve (None, None, None) para accesos/sistema, o una
    recomendación genérica para errores y negocio.
    """
    for regla in REGLAS:
        if categoria in regla["categorias"] and regla["patron"].search(mensaje):
            return regla["id"], regla["severidad"], regla["recomendacion"]

    if categoria == "errores":
        return "error_generico", "media", _RECOMENDACION_GENERICA_ERRORES

    if categoria == "negocio":
        return "negocio_generico", "baja", _RECOMENDACION_GENERICA_NEGOCIO

    return None, None, None


def obtener_titulo_regla(identificador_regla: str) -> str:
    """Devuelve el título corto de una regla, usado para agrupar alertas repetidas."""
    if identificador_regla == "error_generico":
        return "Error no clasificado"
    if identificador_regla == "negocio_generico":
        return "Acción de negocio no clasificada"
    for regla in REGLAS:
        if regla["id"] == identificador_regla:
            return regla["titulo"]
    return "Evento detectado"


def generar_alertas(lineas_por_categoria: dict[str, list[tuple[str, str]]]) -> list[dict]:
    """
    Agrupa líneas de log repetidas del mismo tipo de problema en una sola
    alerta con contador de ocurrencias, en vez de mostrar la misma
    recomendación decenas de veces.

    Recibe: {"seguridad": [(fecha_hora, mensaje), ...], "errores": [...], "negocio": [...]}
    Devuelve una lista de alertas ordenadas de más a menos reciente.
    """
    agrupadas: "OrderedDict[tuple[str, str], dict]" = OrderedDict()

    for categoria, lineas in lineas_por_categoria.items():
        for fecha_hora, mensaje in lineas:
            identificador, severidad, recomendacion = analizar_mensaje(categoria, mensaje)
            if identificador is None:
                continue  # No es un evento relevante para el centro de alertas

            clave_grupo = (categoria, identificador)
            if clave_grupo not in agrupadas:
                agrupadas[clave_grupo] = {
                    "categoria": categoria,
                    "titulo": obtener_titulo_regla(identificador),
                    "severidad": severidad,
                    "recomendacion": recomendacion,
                    "ocurrencias": 0,
                    "ultima_fecha_hora": fecha_hora,
                }
            agrupadas[clave_grupo]["ocurrencias"] += 1

    # Orden de severidad para mostrar primero lo más urgente
    orden_severidad = {"critica": 0, "alta": 1, "media": 2, "baja": 3}
    resultado = list(agrupadas.values())
    resultado.sort(key=lambda alerta: orden_severidad.get(alerta["severidad"], 99))
    return resultado