# Ruta: backend/app/main.py
# Punto de entrada de la API. Funciona en local (uvicorn) y en Vercel (serverless,
# ver backend/api/index.py).
#
# DIFERENCIAS EN VERCEL: el disco es de solo lectura (las imágenes van a la base
# de datos), no hay WebSockets (el bloqueo de mesas es REST, ver routers/mesas.py)
# y el evento "lifespan" no es fiable, por eso la inicialización también se
# dispara en la primera petición de cada instancia.
#
# ORDEN DE MIDDLEWARES (el último declarado es el más externo):
#   CORS -> inicialización -> cabeceras de seguridad -> monitoreo -> bloqueo.
# CORS va afuera para que hasta los 423/500/503 lleven sus cabeceras; el
# monitoreo va afuera del bloqueo para registrar los 423 en seguridad.log.

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

# Bloque: zona horaria de Colombia para todo el proceso (date.today(), datetime.now())
os.environ["TZ"] = "America/Bogota"
try:
    time.tzset()
except AttributeError:
    pass  # Windows no tiene tzset

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.config import configuracion
from app.database import Base, motor, SesionLocal, ES_SQLITE
from app.utils.limitador import limitador
from app.utils.inicializar_admin import crear_administrador_inicial
from app.utils.migraciones import aplicar_migraciones_pendientes
from app.utils.rutas import ruta_absoluta
from app.suscripcion.service import obtener_suscripcion, esta_bloqueado

from app.logs.logger import (
    configurar_logging,
    registrar_acceso,
    registrar_seguridad,
    registrar_error,
    registrar_sistema,
)
from app.logs.router import router as router_logs

from app.routers import (
    archivos,
    auth,
    categorias,
    productos,
    mesas,
    ventas,
    proveedores,
    compras,
    promociones,
    reportes,
    usuarios,
)
from app.routers import finanzas

from escaner.router import router as router_escaner
from QR.router import router as router_qr
from app.suscripcion.router import router as router_suscripcion

logger = logging.getLogger("uvicorn.error")

# --- Rutas que NUNCA se bloquean por vencimiento de suscripción ---
RUTAS_EXCLUIDAS_DE_BLOQUEO = (
    "/api/auth",
    "/api/suscripcion",
    "/api/salud",
    "/uploads",
    "/imagenes",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# Códigos HTTP considerados eventos de seguridad relevantes
CODIGOS_SOSPECHOSOS = {401, 403, 423, 429}

# Identificador arbitrario del candado de PostgreSQL usado al crear tablas
_ID_CANDADO_ESQUEMA = 727274

_estado_inicio = {"listo": False}
_candado_inicio = threading.Lock()


def inicializar_sistema() -> None:
    """
    Prepara la base de datos y los datos iniciales. Es seguro llamarla varias veces:
    solo trabaja la primera vez en cada instancia. En PostgreSQL usa un candado
    transaccional para que dos instancias arrancando a la vez no choquen al crear tablas.
    """
    if _estado_inicio["listo"]:
        return

    with _candado_inicio:
        if _estado_inicio["listo"]:
            return

        try:
            configurar_logging()
        except Exception as error:  # Un fallo de logs no debe impedir el arranque
            logger.warning(f"No se pudo configurar el logging: {error}")

        # Bloque: crea las tablas que aún no existan
        if ES_SQLITE:
            Base.metadata.create_all(bind=motor)
        else:
            with motor.begin() as conexion:
                conexion.execute(text(f"SELECT pg_advisory_xact_lock({_ID_CANDADO_ESQUEMA})"))
                Base.metadata.create_all(bind=conexion)

        # Bloque: agrega columnas faltantes en bases creadas con versiones anteriores
        aplicar_migraciones_pendientes(motor)

        # Bloque: datos iniciales (administrador y registro de suscripción)
        db = SesionLocal()
        try:
            crear_administrador_inicial(db)
            obtener_suscripcion(db)
        finally:
            db.close()

        _estado_inicio["listo"] = True
        registrar_sistema("El sistema se inicializó correctamente")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Arranque del servidor (en Vercel este evento puede no ejecutarse)."""
    await run_in_threadpool(inicializar_sistema)
    yield


# En producción no se publica la documentación interactiva de la API
_docs_activos = not configuracion.es_produccion

app = FastAPI(
    title="API - Sistema de Administración",
    description="Backend con gestión de módulos, autenticación, reportes, control de suscripción mensual, cuentas de pago, monitoreo interno y bloqueo colaborativo de mesas.",
    version="2.0.0",
    lifespan=ciclo_de_vida,
    docs_url="/docs" if _docs_activos else None,
    redoc_url="/redoc" if _docs_activos else None,
    openapi_url="/openapi.json" if _docs_activos else None,
)

# --- Limitador de peticiones (protección contra fuerza bruta y abuso) ---
app.state.limiter = limitador


@app.exception_handler(RateLimitExceeded)
async def manejador_limite_peticiones(request: Request, excepcion: RateLimitExceeded):
    """Registra en seguridad.log cuando una IP supera el límite de peticiones."""
    registrar_seguridad(f"Límite de peticiones excedido en {request.url.path}", request=request)
    return await _rate_limit_exceeded_handler(request, excepcion)


@app.exception_handler(Exception)
async def manejador_errores_no_controlados(request: Request, excepcion: Exception):
    """Captura errores no controlados sin exponer información interna del servidor."""
    logger.error(f"Error no controlado en {request.url.path}: {excepcion}")
    registrar_error(f"{type(excepcion).__name__}: {excepcion}", request=request)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocurrió un error interno en el servidor. Intenta de nuevo más tarde."},
    )


@app.middleware("http")
async def verificar_bloqueo_suscripcion(request: Request, call_next):
    """
    Bloquea toda la API con un 423 (Locked) cuando el ciclo de pago mensual está
    vencido, excepto en las rutas necesarias para iniciar sesión, ver el estado de
    la suscripción y cargar los QR de pago.
    """
    if request.method == "OPTIONS" or any(
        request.url.path.startswith(ruta) for ruta in RUTAS_EXCLUIDAS_DE_BLOQUEO
    ):
        return await call_next(request)

    if request.url.path.startswith("/api"):
        db = SesionLocal()
        try:
            if esta_bloqueado(obtener_suscripcion(db)):
                registrar_seguridad("Intento de uso con el sistema bloqueado por suscripción", request=request)
                return JSONResponse(
                    status_code=423,
                    content={
                        "detail": "El sistema está bloqueado por falta de pago. Comunícate con el proveedor para desbloquearlo."
                    },
                )
        finally:
            db.close()

    return await call_next(request)


@app.middleware("http")
async def registrar_monitoreo(request: Request, call_next):
    """Registra cada petición en accesos.log y los eventos sospechosos en seguridad.log."""
    respuesta = await call_next(request)

    if request.method != "OPTIONS" and not request.url.path.startswith("/uploads"):
        registrar_acceso(request, respuesta.status_code)
        if respuesta.status_code in CODIGOS_SOSPECHOSOS:
            registrar_seguridad(f"Respuesta {respuesta.status_code} en {request.url.path}", request=request)

    return respuesta


@app.middleware("http")
async def agregar_cabeceras_seguridad(request: Request, call_next):
    """Agrega cabeceras HTTP que mitigan XSS, clickjacking y sniffing de tipo MIME."""
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if request.url.path.startswith("/api/escaner"):
        respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    else:
        respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    if configuracion.es_produccion:
        respuesta.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return respuesta


@app.middleware("http")
async def asegurar_inicializacion(request: Request, call_next):
    """
    Garantiza que la base de datos esté lista antes de atender cualquier petición
    (necesario en Vercel, donde no hay evento de arranque fiable).
    """
    if not _estado_inicio["listo"] and request.method != "OPTIONS":
        try:
            await run_in_threadpool(inicializar_sistema)
        except Exception as error:
            logger.error(f"No fue posible inicializar la base de datos: {error}")
            return JSONResponse(
                status_code=503,
                content={"detail": "No fue posible conectar con la base de datos. Intenta de nuevo en unos segundos."},
            )
    return await call_next(request)


# --- CORS: solo los orígenes configurados. Se registra AL FINAL para ser el más externo. ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.lista_origenes_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Clave-Logs"],
)


def _montar_estaticos(ruta_url: str, carpeta_relativa: str, nombre: str) -> None:
    """
    Sirve una carpeta incluida en el despliegue (logo, QR de pago) como archivos
    estáticos, solo si existe. La ruta se resuelve desde la raíz del backend.
    """
    carpeta = ruta_absoluta(carpeta_relativa)
    if os.path.isdir(carpeta):
        app.mount(ruta_url, StaticFiles(directory=carpeta), name=nombre)


# QR de las cuentas de pago. Debe montarse ANTES que "/imagenes" (Starlette resuelve en orden).
_montar_estaticos("/imagenes/cuentas", configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR, "imagenes_cuentas")

# Carpeta general "imagenes" (logo.png, favicon), derivada de la carpeta de cuentas
_montar_estaticos(
    "/imagenes",
    os.path.dirname(configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR.rstrip("/")),
    "imagenes_generales",
)


# --- Registro de routers ---
app.include_router(archivos.router)  # Imágenes de productos desde la base de datos
app.include_router(auth.router)
app.include_router(categorias.router)
app.include_router(productos.router)
app.include_router(mesas.router)
app.include_router(ventas.router)
app.include_router(proveedores.router)
app.include_router(compras.router)
app.include_router(promociones.router)
app.include_router(reportes.router)
app.include_router(usuarios.router)
app.include_router(finanzas.router)
app.include_router(router_escaner)
app.include_router(router_qr)
app.include_router(router_suscripcion)
app.include_router(router_logs)


@app.get("/api/salud", tags=["Sistema"])
def verificar_salud():
    """Endpoint simple para confirmar que la API está activa."""
    return {"estado": "ok"}