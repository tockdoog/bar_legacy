# Ruta: backend/app/logs/logger.py
# Módulo central de monitoreo interno del sistema. Configura archivos de log
# con rotación automática dentro de la carpeta física "~/logs" (accesos,
# seguridad, errores, sistema y negocio) y expone funciones simples para
# registrar eventos desde cualquier parte del backend, evitando duplicar lógica.

import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import configuracion

# --- Carpeta física donde se guardan los archivos de log ---
# Se expande "~" al home real del usuario del sistema operativo.
CARPETA_LOGS = os.path.expanduser(configuracion.CARPETA_LOGS)
os.makedirs(CARPETA_LOGS, exist_ok=True)

# --- Nombres de archivo permitidos (también usado por el router para evitar path traversal) ---
# La categoría "negocio" registra acciones sensibles realizadas por usuarios
# dentro del sistema (cambios de precios, eliminaciones, aperturas de caja,
# devoluciones, etc.), sin importar el tipo de negocio que use el sistema.
ARCHIVOS_LOG = {
    "accesos": "accesos.log",
    "seguridad": "seguridad.log",
    "errores": "errores.log",
    "sistema": "sistema.log",
    "negocio": "negocio.log",
}

# --- Formato estándar de cada línea escrita en los archivos de log ---
_FORMATO = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- Caché de loggers ya construidos, para no crear manejadores duplicados ---
_loggers: dict[str, logging.Logger] = {}


def _construir_logger(categoria: str) -> logging.Logger:
    """
    Crea (una sola vez) un logger con rotación de archivo para una categoría
    específica: accesos, seguridad, errores, sistema o negocio.
    """
    logger = logging.getLogger(f"monitoreo.{categoria}")
    logger.setLevel(configuracion.NIVEL_LOG)
    logger.propagate = False  # Evita que el mensaje también salga por la consola de uvicorn

    if not logger.handlers:
        ruta_archivo = os.path.join(CARPETA_LOGS, ARCHIVOS_LOG[categoria])
        manejador = RotatingFileHandler(
            ruta_archivo,
            maxBytes=configuracion.LOG_MAX_BYTES,
            backupCount=configuracion.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        manejador.setFormatter(_FORMATO)
        logger.addHandler(manejador)

    return logger


def configurar_logging() -> None:
    """Inicializa los 5 loggers al arrancar la aplicación (se llama desde main.py)."""
    for categoria in ARCHIVOS_LOG:
        _loggers[categoria] = _construir_logger(categoria)


def _sanear(texto) -> str:
    """
    Elimina saltos de línea y retornos de carro antes de escribir el mensaje.
    Previene "inyección de logs": evita que un dato controlado por el usuario
    (ej. un nombre de producto) contenga un salto de línea que falsifique una
    línea completa del archivo de log.
    """
    if texto is None:
        return ""
    return str(texto).replace("\r", " ").replace("\n", " ").strip()


def _obtener(categoria: str) -> logging.Logger:
    """Devuelve el logger de la categoría solicitada, creándolo si aún no existe."""
    if categoria not in _loggers:
        _loggers[categoria] = _construir_logger(categoria)
    return _loggers[categoria]


def _ip_cliente(request) -> str:
    """Obtiene la IP real del cliente, considerando si hay un proxy reverso delante."""
    if request is None:
        return "no-disponible"
    adelante = request.headers.get("x-forwarded-for")
    if adelante:
        return adelante.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


# --- Funciones públicas de registro, usadas desde main.py, dependencies.py y routers ---

def registrar_acceso(request, codigo_estado: int, usuario: str = "anonimo") -> None:
    """Registra cada petición HTTP recibida (auditoría general de uso del sistema)."""
    ip = _ip_cliente(request)
    mensaje = (
        f"IP={ip} | usuario={_sanear(usuario)} | {request.method} {request.url.path} "
        f"| estado={codigo_estado}"
    )
    _obtener("accesos").info(mensaje)


def registrar_seguridad(mensaje: str, request=None, usuario: str = "anonimo") -> None:
    """
    Registra eventos sospechosos o relevantes de seguridad: intentos de inicio
    de sesión fallidos, accesos no autorizados, bloqueos por suscripción,
    exceso de peticiones (fuerza bruta), cambios de rol, etc.
    """
    ip = _ip_cliente(request)
    texto = f"IP={ip} | usuario={_sanear(usuario)} | {_sanear(mensaje)}"
    _obtener("seguridad").warning(texto)


def registrar_error(mensaje: str, request=None) -> None:
    """Registra errores no controlados o excepciones capturadas por el backend."""
    if request is not None:
        ip = _ip_cliente(request)
        texto = f"IP={ip} | {request.method} {request.url.path} | {_sanear(mensaje)}"
    else:
        texto = _sanear(mensaje)
    _obtener("errores").error(texto)


def registrar_sistema(mensaje: str, usuario: str = "sistema") -> None:
    """
    Registra eventos administrativos relevantes: arranque/apagado del
    servidor, creación o edición de usuarios, cambios de configuración sensible.
    """
    _obtener("sistema").info(f"usuario={_sanear(usuario)} | {_sanear(mensaje)}")


def registrar_negocio(
    accion: str,
    usuario: str,
    detalle: str | None = None,
    request=None,
) -> None:
    """
    Registra acciones sensibles de negocio realizadas por un usuario dentro
    del sistema: modificación de precios, eliminación de registros, apertura
    o cierre de caja, devoluciones, cambios de inventario manuales, etc.
    Aplica a cualquier tipo de negocio que use el sistema (no está atado a un
    rubro específico).

    Parámetros:
    - accion: descripción corta de la acción (ej. "Modificó el precio de un producto").
    - usuario: nombre de usuario que ejecutó la acción.
    - detalle: información adicional opcional (ej. "Precio anterior: 5.000, nuevo: 6.000").
    - request: objeto Request de FastAPI, para registrar también la IP de origen.
    """
    ip = _ip_cliente(request)
    partes = [f"IP={ip}", f"usuario={_sanear(usuario)}", _sanear(accion)]
    if detalle:
        partes.append(f"detalle={_sanear(detalle)}")
    _obtener("negocio").info(" | ".join(partes))