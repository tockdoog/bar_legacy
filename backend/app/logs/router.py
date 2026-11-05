# Ruta: backend/app/logs/router.py
# Endpoints protegidos (solo administrador + segunda clave de acceso) para
# consultar, filtrar y descargar los archivos de log generados en ~/logs
# (accesos, seguridad, errores, sistema y negocio), así como para obtener
# recomendaciones ante los eventos detectados.

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.config import configuracion
from app.models.usuario import RolUsuario, Usuario
from app.dependencies import requerir_rol
from app.logs.logger import CARPETA_LOGS, ARCHIVOS_LOG, registrar_seguridad, registrar_sistema
from app.logs.recomendaciones import analizar_mensaje, generar_alertas
from app.logs.schemas import (
    CategoriaLog,
    LineaLog,
    ResumenLogs,
    VerificacionClaveLogs,
    AlertaDetectada,
)
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/logs", tags=["Monitoreo"])

# Cantidad de líneas recientes que se analizan para construir el Centro de Alertas
LINEAS_ANALIZADAS_PARA_ALERTAS = 500

# Categorías que se analizan en el Centro de Alertas (seguridad, errores y negocio)
CATEGORIAS_ANALIZADAS_EN_ALERTAS = (CategoriaLog.SEGURIDAD, CategoriaLog.ERRORES, CategoriaLog.NEGOCIO)


def _ruta_archivo(categoria: CategoriaLog) -> str:
    """Construye la ruta del archivo a partir del Enum (nunca de texto libre del usuario)."""
    return os.path.join(CARPETA_LOGS, ARCHIVOS_LOG[categoria.value])


def _leer_ultimas_lineas(categoria: CategoriaLog, cantidad: int) -> list[str]:
    """Lee las últimas N líneas crudas de un archivo de log, o lista vacía si no existe."""
    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
        todas_las_lineas = archivo.readlines()
    ultimas = todas_las_lineas[-cantidad:]
    ultimas.reverse()  # De la más reciente a la más antigua
    return ultimas


def _parsear_linea(linea: str, categoria: str) -> LineaLog | None:
    """
    Convierte una línea cruda 'fecha | NIVEL | mensaje' en un objeto
    estructurado, agregando la severidad y recomendación detectadas para esa
    categoría de log específica.
    """
    partes = linea.strip().split(" | ", 2)
    if len(partes) < 3:
        return None

    fecha_hora, nivel, mensaje = partes
    _identificador, severidad, recomendacion = analizar_mensaje(categoria, mensaje)

    return LineaLog(
        fecha_hora=fecha_hora,
        nivel=nivel,
        mensaje=mensaje,
        severidad=severidad,
        recomendacion=recomendacion,
    )


def verificar_clave_logs(
    request: Request,
    x_clave_logs: str | None = Header(default=None, alias="X-Clave-Logs"),
) -> bool:
    """
    Segunda barrera de seguridad exclusiva del panel de logs: exige una clave
    independiente de la contraseña normal del usuario, definida en el .env.
    Se valida en CADA petición (no solo al entrar), usando comparación segura
    contra ataques de temporización (secrets.compare_digest).
    """
    if not x_clave_logs or not secrets.compare_digest(x_clave_logs, configuracion.CLAVE_ACCESO_LOGS):
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
    contenido en el frontend. Limitado a 5 intentos por minuto por IP para
    frenar ataques de fuerza bruta sobre esta clave.
    """
    if not secrets.compare_digest(datos.clave, configuracion.CLAVE_ACCESO_LOGS):
        registrar_seguridad(
            "Intento fallido de ingreso al panel de logs", request=request, usuario=usuario.nombre_usuario
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave de acceso incorrecta")

    registrar_sistema("Acceso concedido al panel de monitoreo de logs", usuario=usuario.nombre_usuario)
    return {"acceso": True}


# --- 2) Resumen general (tamaño y líneas de cada archivo) ---
@router.get("/", response_model=list[ResumenLogs])
def resumen_logs(
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """Devuelve un resumen (tamaño, cantidad de líneas, última modificación) de cada categoría."""
    resultado = []
    for categoria in CategoriaLog:
        ruta = _ruta_archivo(categoria)

        if not os.path.exists(ruta):
            resultado.append(
                ResumenLogs(categoria=categoria, total_lineas=0, peso_archivo_kb=0, ultima_modificacion=None)
            )
            continue

        with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
            total_lineas = sum(1 for _ in archivo)

        peso_kb = round(os.path.getsize(ruta) / 1024, 2)
        ultima_modificacion = datetime.fromtimestamp(
            os.path.getmtime(ruta), tz=timezone.utc
        ).isoformat()

        resultado.append(
            ResumenLogs(
                categoria=categoria,
                total_lineas=total_lineas,
                peso_archivo_kb=peso_kb,
                ultima_modificacion=ultima_modificacion,
            )
        )
    return resultado


# --- 3) Centro de Alertas: DEBE declararse antes que "/{categoria}" ---
@router.get("/alertas/resumen", response_model=list[AlertaDetectada])
def resumen_alertas(
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """
    Centro de Alertas: analiza las líneas más recientes de seguridad.log,
    errores.log y negocio.log, agrupa los problemas repetidos en una sola
    alerta con contador, y devuelve la recomendación de qué hacer para cada
    tipo de evento detectado. Se muestra al principio del panel de monitoreo.
    """
    lineas_por_categoria: dict[str, list[tuple[str, str]]] = {}

    for categoria in CATEGORIAS_ANALIZADAS_EN_ALERTAS:
        lineas_crudas = _leer_ultimas_lineas(categoria, LINEAS_ANALIZADAS_PARA_ALERTAS)
        lineas_interpretadas = []
        for linea in lineas_crudas:
            partes = linea.strip().split(" | ", 2)
            if len(partes) < 3:
                continue
            fecha_hora, _nivel, mensaje = partes
            lineas_interpretadas.append((fecha_hora, mensaje))
        lineas_por_categoria[categoria.value] = lineas_interpretadas

    alertas = generar_alertas(lineas_por_categoria)
    return [AlertaDetectada(**alerta) for alerta in alertas]


# --- 4) Consulta de un log específico (ruta genérica, va DESPUÉS de "/alertas/resumen") ---
@router.get("/{categoria}", response_model=list[LineaLog])
def consultar_log(
    categoria: CategoriaLog,
    lineas: int = Query(default=200, ge=1, le=1000, description="Cantidad de líneas más recientes a devolver"),
    busqueda: str | None = Query(default=None, max_length=100, description="Texto a buscar dentro del mensaje"),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """
    Devuelve las últimas N líneas del log solicitado (de la más reciente a la
    más antigua), con filtro opcional de texto y, cuando aplica, severidad y
    recomendación. Requiere rol administrador y la clave especial del panel.
    """
    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        return []

    with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
        todas_las_lineas = archivo.readlines()

    if busqueda:
        busqueda_normalizada = busqueda.lower()
        todas_las_lineas = [l for l in todas_las_lineas if busqueda_normalizada in l.lower()]

    ultimas = todas_las_lineas[-lineas:]
    ultimas.reverse()

    lineas_parseadas = [_parsear_linea(l, categoria.value) for l in ultimas]
    return [l for l in lineas_parseadas if l is not None]


# --- 5) Descarga del archivo de log completo ---
@router.get("/{categoria}/descargar")
def descargar_log(
    categoria: CategoriaLog,
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
    _acceso_verificado: bool = Depends(verificar_clave_logs),
):
    """Permite descargar el archivo de log completo (ej. para enviarlo a soporte técnico)."""
    ruta = _ruta_archivo(categoria)
    if not os.path.exists(ruta):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aún no existe ese archivo de log")

    return FileResponse(
        path=ruta,
        filename=ARCHIVOS_LOG[categoria.value],
        media_type="text/plain",
    )