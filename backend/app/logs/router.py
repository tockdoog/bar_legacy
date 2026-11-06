# Ruta: backend/app/logs/router.py
# Endpoints protegidos (solo administrador + segunda clave de acceso) para
# consultar, filtrar y descargar los registros del monitoreo interno (accesos,
# seguridad, errores, sistema y negocio) y obtener recomendaciones ante los
# eventos detectados.
#
# ORIGEN DE LOS DATOS: en local se leen los archivos de log; en Vercel se leen de
# la tabla registros_log (ver logs/logger.py). En Vercel la categoría "accesos" no
# se guarda en la base: se consulta en el panel de Vercel (proyecto > Logs).

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import configuracion
from app.database import obtener_db
from app.dependencies import requerir_rol
from app.logs.logger import (
    ARCHIVOS_LOG,
    CARPETA_LOGS,
    CATEGORIAS_EN_BASE_DATOS,
    GUARDAR_EN_BASE_DATOS,
    registrar_seguridad,
    registrar_sistema,
)
from app.logs.recomendaciones import analizar_mensaje, generar_alertas
from app.logs.schemas import (
    AlertaDetectada,
    CategoriaLog,
    LineaLog,
    ResumenLogs,
    VerificacionClaveLogs,
)
from app.models.registro_log import RegistroLog
from app.models.usuario import RolUsuario, Usuario
from app.utils.limitador import limitador
from app.utils.zona_horaria import ZONA_HORARIA_COLOMBIA

router = APIRouter(prefix="/api/logs", tags=["Monitoreo"])

# Cantidad de líneas recientes que se analizan para construir el Centro de Alertas
LINEAS_ANALIZADAS_PARA_ALERTAS = 500

# Categorías que se analizan en el Centro de Alertas (seguridad, errores y negocio)
CATEGORIAS_ANALIZADAS_EN_ALERTAS = (CategoriaLog.SEGURIDAD, CategoriaLog.ERRORES, CategoriaLog.NEGOCIO)

# Formato de fecha mostrado en el panel y usado al descargar
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

# Máximo de filas que entrega la descarga cuando los datos están en la base
LIMITE_FILAS_DESCARGA = 5000


# =============================================================================
# LECTURA DE REGISTROS (archivo en local, base de datos en Vercel)
# Cada registro es una tupla (fecha_hora, nivel, mensaje), del más reciente al más antiguo.
# =============================================================================

def _ruta_archivo(categoria: CategoriaLog) -> str:
    """Construye la ruta del archivo a partir del Enum (nunca de texto libre del usuario)."""
    return os.path.join(CARPETA_LOGS, ARCHIVOS_LOG[categoria.value])


def _leer_registros_de_archivo(categoria: CategoriaLog, cantidad: int, busqueda: str | None) -> list[tuple[str, str, str]]:
    """Lee el archivo de log, filtra por texto, toma las últimas N líneas y las interpreta."""
    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        return []

    with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
        lineas = archivo.readlines()

    if busqueda:
        texto = busqueda.lower()
        lineas = [linea for linea in lineas if texto in linea.lower()]

    ultimas = lineas[-cantidad:]
    ultimas.reverse()  # De la más reciente a la más antigua

    registros = []
    for linea in ultimas:
        partes = linea.strip().split(" | ", 2)
        if len(partes) == 3:  # Las líneas mal formadas se descartan
            registros.append((partes[0], partes[1], partes[2]))
    return registros


def _leer_registros_de_base(db: Session, categoria: CategoriaLog, cantidad: int, busqueda: str | None) -> list[tuple[str, str, str]]:
    """Lee los últimos N registros de la categoría desde la tabla registros_log."""
    if categoria.value not in CATEGORIAS_EN_BASE_DATOS:
        return []

    consulta = db.query(RegistroLog).filter(RegistroLog.categoria == categoria.value)
    if busqueda:
        # autoescape evita que "%" o "_" escritos por el usuario actúen como comodines
        consulta = consulta.filter(func.lower(RegistroLog.mensaje).contains(busqueda.lower(), autoescape=True))

    filas = consulta.order_by(RegistroLog.id.desc()).limit(cantidad).all()
    return [(fila.fecha.strftime(FORMATO_FECHA), fila.nivel, fila.mensaje) for fila in filas]


def _leer_registros(db: Session, categoria: CategoriaLog, cantidad: int, busqueda: str | None = None) -> list[tuple[str, str, str]]:
    """Punto único de lectura: elige el origen de datos según el entorno."""
    if GUARDAR_EN_BASE_DATOS:
        return _leer_registros_de_base(db, categoria, cantidad, busqueda)
    return _leer_registros_de_archivo(categoria, cantidad, busqueda)


def _a_linea_log(registro: tuple[str, str, str], categoria: str) -> LineaLog:
    """Convierte un registro en su respuesta, agregando severidad y recomendación detectadas."""
    fecha_hora, nivel, mensaje = registro
    _identificador, severidad, recomendacion = analizar_mensaje(categoria, mensaje)
    return LineaLog(
        fecha_hora=fecha_hora,
        nivel=nivel,
        mensaje=mensaje,
        severidad=severidad,
        recomendacion=recomendacion,
    )


# =============================================================================
# RESUMEN POR CATEGORÍA
# =============================================================================

def _resumen_de_archivo(categoria: CategoriaLog) -> ResumenLogs:
    """Tamaño, cantidad de líneas y última modificación del archivo de una categoría."""
    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        return ResumenLogs(categoria=categoria, total_lineas=0, peso_archivo_kb=0, ultima_modificacion=None)

    with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
        total_lineas = sum(1 for _ in archivo)

    return ResumenLogs(
        categoria=categoria,
        total_lineas=total_lineas,
        peso_archivo_kb=round(os.path.getsize(ruta) / 1024, 2),
        ultima_modificacion=datetime.fromtimestamp(os.path.getmtime(ruta), tz=timezone.utc).isoformat(),
    )


def _resumen_de_base(db: Session, categoria: CategoriaLog) -> ResumenLogs:
    """Cantidad de registros, peso aproximado y fecha del último evento de una categoría."""
    if categoria.value not in CATEGORIAS_EN_BASE_DATOS:
        return ResumenLogs(categoria=categoria, total_lineas=0, peso_archivo_kb=0, ultima_modificacion=None)

    total, caracteres, ultima = (
        db.query(
            func.count(RegistroLog.id),
            func.coalesce(func.sum(func.length(RegistroLog.mensaje)), 0),
            func.max(RegistroLog.fecha),
        )
        .filter(RegistroLog.categoria == categoria.value)
        .one()
    )
    return ResumenLogs(
        categoria=categoria,
        total_lineas=total,
        peso_archivo_kb=round(caracteres / 1024, 2),
        ultima_modificacion=ultima.replace(tzinfo=ZONA_HORARIA_COLOMBIA).isoformat() if ultima else None,
    )


# =============================================================================
# SEGURIDAD DEL PANEL
# =============================================================================

def verificar_clave_logs(
    request: Request,
    x_clave_logs: str | None = Header(default=None, alias="X-Clave-Logs"),
) -> bool:
    """
    Segunda barrera de seguridad exclusiva del panel de logs: exige una clave
    independiente de la contraseña normal del usuario, definida en las variables
    de entorno. Se valida en CADA petición (no solo al entrar), con comparación
    segura contra ataques de temporización (secrets.compare_digest).
    """
    if not x_clave_logs or not secrets.compare_digest(
        x_clave_logs.encode("utf-8"), configuracion.CLAVE_ACCESO_LOGS.encode("utf-8")
    ):
        registrar_seguridad("Intento de acceso al panel de logs con clave inválida o ausente", request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de acceso al panel de logs incorrecta",
        )
    return True


# --- 1) Verificación de la clave especial del panel de logs ---
@router.post("/verificar-acceso", status_code=status.HTTP_200_OK)
@limitador.limit("5/minute")
def verificar_acceso(
    request: Request,
    datos: VerificacionClaveLogs,
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """
    Valida la clave especial del panel de logs antes de mostrar cualquier
    contenido en el frontend. Limitado a 5 intentos por minuto por IP.
    """
    if not secrets.compare_digest(
        datos.clave.encode("utf-8"), configuracion.CLAVE_ACCESO_LOGS.encode("utf-8")
    ):
        registrar_seguridad(
            "Intento fallido de ingreso al panel de logs", request=request, usuario=usuario.nombre_usuario
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave de acceso incorrecta")

    registrar_sistema("Acceso concedido al panel de monitoreo de logs", usuario=usuario.nombre_usuario)
    return {"acceso": True}


# --- 2) Resumen general (tamaño y líneas de cada categoría) ---
@router.get("/", response_model=list[ResumenLogs])
def resumen_logs(
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """Devuelve un resumen (tamaño, cantidad de líneas, última modificación) de cada categoría."""
    if GUARDAR_EN_BASE_DATOS:
        return [_resumen_de_base(db, categoria) for categoria in CategoriaLog]
    return [_resumen_de_archivo(categoria) for categoria in CategoriaLog]


# --- 3) Centro de Alertas: DEBE declararse antes que "/{categoria}" ---
@router.get("/alertas/resumen", response_model=list[AlertaDetectada])
def resumen_alertas(
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """
    Centro de Alertas: analiza los registros más recientes de seguridad, errores y
    negocio, agrupa los problemas repetidos en una sola alerta con contador y
    devuelve la recomendación de qué hacer para cada tipo de evento detectado.
    """
    lineas_por_categoria: dict[str, list[tuple[str, str]]] = {}

    for categoria in CATEGORIAS_ANALIZADAS_EN_ALERTAS:
        registros = _leer_registros(db, categoria, LINEAS_ANALIZADAS_PARA_ALERTAS)
        lineas_por_categoria[categoria.value] = [(fecha, mensaje) for fecha, _nivel, mensaje in registros]

    alertas = generar_alertas(lineas_por_categoria)
    return [AlertaDetectada(**alerta) for alerta in alertas]


# --- 4) Consulta de un log específico (ruta genérica, va DESPUÉS de "/alertas/resumen") ---
@router.get("/{categoria}", response_model=list[LineaLog])
def consultar_log(
    categoria: CategoriaLog,
    lineas: int = Query(default=200, ge=1, le=1000, description="Cantidad de líneas más recientes a devolver"),
    busqueda: str | None = Query(default=None, max_length=100, description="Texto a buscar dentro del mensaje"),
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """
    Devuelve los últimos N registros de la categoría (del más reciente al más
    antiguo), con filtro opcional de texto, severidad y recomendación. Requiere
    rol administrador y la clave especial del panel.
    """
    registros = _leer_registros(db, categoria, lineas, busqueda)
    return [_a_linea_log(registro, categoria.value) for registro in registros]


# --- 5) Descarga del registro completo de una categoría ---
@router.get("/{categoria}/descargar")
def descargar_log(
    categoria: CategoriaLog,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """Permite descargar el registro (ej. para enviarlo a soporte técnico)."""
    nombre_archivo = ARCHIVOS_LOG[categoria.value]

    if GUARDAR_EN_BASE_DATOS:
        if categoria.value not in CATEGORIAS_EN_BASE_DATOS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Los accesos se consultan en el panel de Vercel (proyecto > Logs).",
            )
        registros = _leer_registros_de_base(db, categoria, LIMITE_FILAS_DESCARGA, None)
        registros.reverse()  # Orden cronológico en el archivo descargado
        contenido = "\n".join(f"{fecha} | {nivel} | {mensaje}" for fecha, nivel, mensaje in registros)
        return PlainTextResponse(
            contenido,
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
        )

    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aún no existe ese archivo de log")

    return FileResponse(path=ruta, filename=nombre_archivo, media_type="text/plain")