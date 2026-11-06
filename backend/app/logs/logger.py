# Ruta: backend/app/logs/logger.py
# Módulo central de monitoreo interno. Expone funciones simples para registrar
# eventos (accesos, seguridad, errores, sistema y negocio) desde cualquier parte
# del backend.
#
# DÓNDE SE GUARDA CADA COSA:
# - Local: archivos con rotación automática en la carpeta configurada (~/logs).
# - Vercel: el disco no persiste ni se comparte entre instancias, por eso
#   seguridad, errores, sistema y negocio se guardan en la base de datos
#   (tabla registros_log, se conservan 30 días) y además salen por la consola.
#   Los accesos (uno por petición) solo salen por la consola de Vercel.

import logging
import os
import sys
import tempfile
import threading
import time
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from app.config import configuracion
from app.database import SesionLocal
from app.models.registro_log import RegistroLog
from app.utils.limitador import obtener_ip_cliente
from app.utils.zona_horaria import ahora_colombia

# --- Bloque: modo de almacenamiento según el entorno ---
GUARDAR_EN_BASE_DATOS = bool(os.environ.get("VERCEL"))
CATEGORIAS_EN_BASE_DATOS = {"seguridad", "errores", "sistema", "negocio"}

# --- Bloque: límites del almacenamiento en base de datos ---
DIAS_RETENCION_REGISTROS = 30
PURGA_CADA_N_REGISTROS = 200
MAXIMO_CARACTERES_MENSAJE = 1000
SEGUNDOS_SIN_REPETIR_SEGURIDAD = 30  # Un mismo evento de seguridad no se repite dentro de esta ventana
SEGUNDOS_PAUSA_SI_BASE_FALLA = 60  # Si la base falla, no se reintenta de inmediato (evita bloqueos)


def _resolver_carpeta_logs() -> str:
    """Devuelve la primera carpeta de logs escribible: la configurada o /tmp/logs."""
    candidatas = (
        os.path.expanduser(configuracion.CARPETA_LOGS),
        os.path.join(tempfile.gettempdir(), "logs"),
    )
    for ruta in candidatas:
        try:
            os.makedirs(ruta, exist_ok=True)
            if os.access(ruta, os.W_OK):
                return ruta
        except OSError:
            continue
    return candidatas[-1]


# --- Carpeta física de los archivos de log (solo se usa fuera de Vercel) ---
CARPETA_LOGS = _resolver_carpeta_logs()

# --- Nombres de archivo permitidos (también usado por el router para evitar path traversal) ---
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

# --- Estado interno compartido por los manejadores de base de datos ---
_loggers: dict[str, logging.Logger] = {}
_candado_estado = threading.Lock()
_ultimos_mensajes: dict[tuple[str, str], float] = {}
_registros_desde_purga = 0
_base_pausada_hasta = 0.0


def _es_repetido(categoria: str, mensaje: str) -> bool:
    """True si el mismo mensaje ya se guardó hace menos de SEGUNDOS_SIN_REPETIR_SEGURIDAD."""
    ahora = time.monotonic()
    with _candado_estado:
        if len(_ultimos_mensajes) > 500:
            _ultimos_mensajes.clear()  # Evita que el diccionario crezca sin límite
        previo = _ultimos_mensajes.get((categoria, mensaje))
        if previo is not None and ahora - previo < SEGUNDOS_SIN_REPETIR_SEGURIDAD:
            return True
        _ultimos_mensajes[(categoria, mensaje)] = ahora
        return False


def _purgar_registros_antiguos(db) -> None:
    """Cada cierto número de inserciones borra los registros más viejos que la retención."""
    global _registros_desde_purga
    with _candado_estado:
        _registros_desde_purga += 1
        if _registros_desde_purga < PURGA_CADA_N_REGISTROS:
            return
        _registros_desde_purga = 0

    limite = ahora_colombia() - timedelta(days=DIAS_RETENCION_REGISTROS)
    db.query(RegistroLog).filter(RegistroLog.fecha < limite).delete(synchronize_session=False)
    db.commit()


class ManejadorBaseDatos(logging.Handler):
    """Manejador de logging que guarda cada evento como una fila de registros_log."""

    def __init__(self, categoria: str, deduplicar: bool = False):
        super().__init__()
        self.categoria = categoria
        self.deduplicar = deduplicar

    def emit(self, record: logging.LogRecord) -> None:
        """Guarda el evento. Un fallo de la base nunca debe romper la petición que lo originó."""
        global _base_pausada_hasta
        if time.monotonic() < _base_pausada_hasta:
            return  # La base falló hace poco: el evento igual queda en la consola

        try:
            mensaje = record.getMessage()[:MAXIMO_CARACTERES_MENSAJE]
            if self.deduplicar and _es_repetido(self.categoria, mensaje):
                return

            db = SesionLocal()
            try:
                db.add(
                    RegistroLog(
                        categoria=self.categoria,
                        fecha=ahora_colombia(),
                        nivel=record.levelname,
                        mensaje=mensaje,
                    )
                )
                db.commit()
                _purgar_registros_antiguos(db)
            finally:
                db.close()
        except Exception:
            _base_pausada_hasta = time.monotonic() + SEGUNDOS_PAUSA_SI_BASE_FALLA
            self.handleError(record)


def _agregar_consola(logger: logging.Logger, categoria: str) -> None:
    """Envía el evento también a la salida estándar (visible en Vercel > Logs)."""
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(logging.Formatter(f"[{categoria}] %(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(consola)


def _construir_logger(categoria: str) -> logging.Logger:
    """Crea (una sola vez) el logger de una categoría con los manejadores del entorno."""
    logger = logging.getLogger(f"monitoreo.{categoria}")
    logger.setLevel(configuracion.NIVEL_LOG)
    logger.propagate = False  # Evita que el mensaje también salga por la consola de uvicorn

    if logger.handlers:
        return logger

    if GUARDAR_EN_BASE_DATOS:
        # Vercel: base de datos (si la categoría lo admite) y consola
        if categoria in CATEGORIAS_EN_BASE_DATOS:
            logger.addHandler(ManejadorBaseDatos(categoria, deduplicar=(categoria == "seguridad")))
        _agregar_consola(logger, categoria)
        return logger

    # Local: archivo con rotación; si no se puede escribir, queda solo la consola
    try:
        manejador = RotatingFileHandler(
            os.path.join(CARPETA_LOGS, ARCHIVOS_LOG[categoria]),
            maxBytes=configuracion.LOG_MAX_BYTES,
            backupCount=configuracion.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        manejador.setFormatter(_FORMATO)
        logger.addHandler(manejador)
    except OSError:
        _agregar_consola(logger, categoria)
    return logger


def configurar_logging() -> None:
    """Inicializa los 5 loggers al arrancar la aplicación (se llama desde main.py)."""
    for categoria in ARCHIVOS_LOG:
        _loggers[categoria] = _construir_logger(categoria)


def _sanear(texto) -> str:
    """
    Elimina saltos de línea y retornos de carro antes de registrar el mensaje.
    Previene "inyección de logs": un dato controlado por el usuario no puede
    falsificar una línea completa del registro.
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
    """IP real del cliente (misma lógica segura que el limitador de peticiones)."""
    if request is None:
        return "no-disponible"
    return obtener_ip_cliente(request)


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
    """Registra eventos sospechosos o relevantes de seguridad."""
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
    """Registra eventos administrativos relevantes: arranque, usuarios, configuración."""
    _obtener("sistema").info(f"usuario={_sanear(usuario)} | {_sanear(mensaje)}")


def registrar_negocio(
    accion: str,
    usuario: str,
    detalle: str | None = None,
    request=None,
) -> None:
    """
    Registra acciones sensibles de negocio realizadas por un usuario (cambios de
    precios, eliminaciones, anulaciones, compras, etc.).

    - accion: descripción corta de la acción.
    - usuario: nombre de usuario que ejecutó la acción.
    - detalle: información adicional opcional.
    - request: objeto Request de FastAPI, para registrar también la IP de origen.
    """
    ip = _ip_cliente(request)
    partes = [f"IP={ip}", f"usuario={_sanear(usuario)}", _sanear(accion)]
    if detalle:
        partes.append(f"detalle={_sanear(detalle)}")
    _obtener("negocio").info(" | ".join(partes))