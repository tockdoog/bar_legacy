# Ruta: backend/app/main.py
# Punto de entrada de la API. Funciona en local (uvicorn) y en Vercel
# (serverless, ver backend/api/index.py).
#
# DIFERENCIAS EN VERCEL:
# - Los WebSockets no están soportados: el módulo de mesas en tiempo real se
#   desactiva y el frontend sincroniza las mesas por consulta periódica.
# - El disco es de solo lectura: la creación de carpetas se intenta sin fallar.
# - El evento "lifespan" no es fiable: la inicialización (tablas, admin,
#   suscripción) se ejecuta una vez por instancia, la primera vez que se necesita.
# - CORS se registra al final para ser el middleware más externo, de modo que
#   también agregue sus cabeceras a las respuestas 423 y 500.

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

# Bloque: fija la zona horaria de Colombia para todo el proceso. Hace que
# date.today() y datetime.now() devuelvan hora de Bogotá aunque el servidor
# (Vercel, Docker) esté en UTC.
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
from app.database import Base, motor, SesionLocal, ES_SQLITE, ES_VERCEL
from app.utils.limitador import limitador
from app.utils.inicializar_admin import crear_administrador_inicial
from app.utils.migraciones import aplicar_migraciones_pendientes
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

# Solo se importa el módulo de WebSockets fuera de Vercel
if not ES_VERCEL:
    from app.mesas_realtime.router import router as router_mesas_tiempo_real
    from app.mesas_realtime.gestor_bloqueos import tarea_periodica_expiracion_bloqueos

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


def _crear_carpeta_si_es_posible(ruta: str) -> None:
    """Crea una carpeta; si el disco es de solo lectura (Vercel), lo ignora."""
    try:
        os.makedirs(ruta, exist_ok=True)
    except OSError:
        pass


def inicializar_sistema() -> None:
    """
    Prepara la base de datos y los datos iniciales. Es seguro llamarla varias
    veces: solo trabaja la primera vez en cada instancia. En PostgreSQL usa un
    candado transaccional para que dos instancias arrancando a la vez no
    choquen al crear las tablas.
    """
    if _estado_inicio["listo"]:
        return

    with _candado_inicio:
        if _estado_inicio["listo"]:
            return

        try:
            configurar_logging()
        except Exception as error:  # Un fallo de logs no debe impedir el arranque
            logger.warning(f"No se pudo configurar el logging en archivos: {error}")

        # Bloque: crea las tablas que aún no existan
        if ES_SQLITE:
            Base.metadata.create_all(bind=motor)
        else:
            with motor.begin() as conexion:
                conexion.execute(text(f"SELECT pg_advisory_xact_lock({_ID_CANDADO_ESQUEMA})"))
                Base.metadata.create_all(bind=conexion)

        # Bloque: agrega columnas faltantes en bases creadas con versiones anteriores
        aplicar_migraciones_pendientes(motor)

        _crear_carpeta_si_es_posible(configuracion.CARPETA_IMAGENES_PRODUCTOS)
        _crear_carpeta_si_es_posible(configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR)

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
    """Arranque y apagado del servidor (en Vercel este evento puede no ejecutarse)."""
    await run_in_threadpool(inicializar_sistema)

    # La liberación automática de bloqueos de mesa solo existe fuera de Vercel
    tarea_expiracion = None
    if not ES_VERCEL:
        tarea_expiracion = asyncio.create_task(tarea_periodica_expiracion_bloqueos())

    yield

    if tarea_expiracion:
        tarea_expiracion.cancel()


app = FastAPI(
    title="API - Sistema de Administración",
    description="Backend con gestión de módulos, autenticación, reportes, control de suscripción mensual, cuentas de pago, monitoreo interno y vinculación de dispositivos por QR.",
    version="1.7.0",
    lifespan=ciclo_de_vida,
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
async def registrar_monitoreo(request: Request, call_next):
    """Registra cada petición en accesos.log y los eventos sospechosos en seguridad.log."""
    respuesta = await call_next(request)

    if request.method != "OPTIONS" and not request.url.path.startswith("/uploads"):
        registrar_acceso(request, respuesta.status_code)

        if respuesta.status_code in CODIGOS_SOSPECHOSOS:
            registrar_seguridad(f"Respuesta {respuesta.status_code} en {request.url.path}", request=request)

    return respuesta


@app.middleware("http")
async def verificar_bloqueo_suscripcion(request: Request, call_next):
    """
    Bloquea toda la API con un 423 (Locked) cuando el ciclo de pago mensual
    está vencido, excepto en las rutas necesarias para iniciar sesión, ver el
    estado de la suscripción y cargar los QR de pago.
    """
    if request.method == "OPTIONS" or any(
        request.url.path.startswith(ruta) for ruta in RUTAS_EXCLUIDAS_DE_BLOQUEO
    ):
        return await call_next(request)

    if request.url.path.startswith("/api"):
        db = SesionLocal()
        try:
            suscripcion = obtener_suscripcion(db)
            if esta_bloqueado(suscripcion):
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
async def asegurar_inicializacion(request: Request, call_next):
    """
    Garantiza que la base de datos esté lista antes de atender cualquier
    petición (necesario en Vercel, donde no hay evento de arranque fiable).
    Se declara después de los demás para ejecutarse antes que ellos.
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


# --- CORS: solo se permiten los orígenes configurados en las variables de entorno.
# Se registra AL FINAL para ser el middleware más externo (ver nota al inicio). ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.lista_origenes_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Clave-Logs"],
)


def _montar_estaticos(ruta_url: str, carpeta: str, nombre: str) -> None:
    """
    Sirve una carpeta como archivos estáticos solo si existe. En Vercel, la
    carpeta de imágenes subidas no existe (disco de solo lectura), y montar
    una carpeta inexistente haría fallar el arranque completo.
    """
    _crear_carpeta_si_es_posible(carpeta)
    if os.path.isdir(carpeta):
        app.mount(ruta_url, StaticFiles(directory=carpeta), name=nombre)


# Imágenes de productos ya procesadas
_montar_estaticos("/uploads/productos", configuracion.CARPETA_IMAGENES_PRODUCTOS, "imagenes_productos")

# QR de las cuentas de pago del proveedor. Debe montarse ANTES que "/imagenes",
# porque Starlette resuelve los montajes en el orden en que se registran.
_montar_estaticos("/imagenes/cuentas", configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR, "imagenes_cuentas")

# Carpeta general "imagenes" (logo.png, favicon), derivada de la carpeta de cuentas
CARPETA_IMAGENES_BASE = os.path.dirname(configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR.rstrip("/"))
_montar_estaticos("/imagenes", CARPETA_IMAGENES_BASE, "imagenes_generales")


# --- Registro de routers del núcleo de la API ---
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

# Mesas en tiempo real (WebSocket): solo disponible fuera de Vercel
if not ES_VERCEL:
    app.include_router(router_mesas_tiempo_real)


@app.get("/api/salud", tags=["Sistema"])
def verificar_salud():
    """Endpoint simple para confirmar que la API está activa."""
    return {"estado": "ok"}