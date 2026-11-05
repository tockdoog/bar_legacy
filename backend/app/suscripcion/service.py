# Ruta: backend/app/suscripcion/service.py
# Lógica de negocio del módulo de suscripción: obtener/crear el registro de
# pago, calcular días restantes, determinar si el sistema debe bloquearse,
# procesar los intentos de desbloqueo con protección contra fuerza bruta, y
# listar las cuentas de pago fijas del proveedor del software (definidas en
# cuentas_proveedor.py, no en base de datos).

import math
import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import configuracion
from app.suscripcion.cuentas_proveedor import CUENTAS_PROVEEDOR
from app.suscripcion.models import Suscripcion
from app.suscripcion.schemas import CuentaProveedorRespuesta

# Identificador fijo: solo existe un registro de suscripción para todo el sistema
ID_SUSCRIPCION_UNICA = 1


def _normalizar_utc(fecha: datetime) -> datetime:
    """
    Garantiza que una fecha tenga zona horaria UTC. SQLite no conserva de forma
    confiable la zona horaria al guardar/leer, por lo que se asume UTC cuando
    la fecha llega "ingenua" (sin tzinfo), evitando errores al comparar fechas.
    """
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def obtener_suscripcion(db: Session) -> Suscripcion:
    """
    Devuelve el registro único de suscripción. Si es la primera vez que arranca
    el sistema, lo crea con un ciclo nuevo que inicia hoy.
    """
    suscripcion = db.query(Suscripcion).filter(Suscripcion.id == ID_SUSCRIPCION_UNICA).first()

    if suscripcion is None:
        ahora = datetime.now(timezone.utc)
        suscripcion = Suscripcion(
            id=ID_SUSCRIPCION_UNICA,
            fecha_inicio=ahora,
            fecha_vencimiento=ahora + timedelta(days=configuracion.DIAS_SUSCRIPCION),
        )
        db.add(suscripcion)
        db.commit()
        db.refresh(suscripcion)

    return suscripcion


def calcular_dias_restantes(suscripcion: Suscripcion) -> int:
    """Calcula cuántos días completos faltan para el vencimiento (0 si ya venció)."""
    ahora = datetime.now(timezone.utc)
    vencimiento = _normalizar_utc(suscripcion.fecha_vencimiento)
    segundos_restantes = (vencimiento - ahora).total_seconds()

    if segundos_restantes <= 0:
        return 0

    return math.ceil(segundos_restantes / 86400)


def esta_bloqueado(suscripcion: Suscripcion) -> bool:
    """El sistema se bloquea automáticamente en el instante en que vence la suscripción."""
    ahora = datetime.now(timezone.utc)
    return ahora >= _normalizar_utc(suscripcion.fecha_vencimiento)


def intentar_desbloqueo(db: Session, clave_ingresada: str) -> tuple[bool, str]:
    """
    Valida la contraseña maestra de desbloqueo (proporcionada por ti, el
    proveedor del software, cuando el cliente ya pagó) y, si es correcta,
    renueva el ciclo de suscripción por un mes más a partir de este momento.

    Seguridad aplicada:
    - Comparación con secrets.compare_digest para evitar ataques de temporización.
    - Bloqueo temporal tras varios intentos fallidos (fuerza bruta sobre la clave).
    - La clave nunca se registra en logs ni se refleja en los mensajes de error.
    """
    suscripcion = obtener_suscripcion(db)
    ahora = datetime.now(timezone.utc)

    if suscripcion.bloqueado_hasta and ahora < _normalizar_utc(suscripcion.bloqueado_hasta):
        minutos_restantes = math.ceil(
            (_normalizar_utc(suscripcion.bloqueado_hasta) - ahora).total_seconds() / 60
        )
        return False, f"Demasiados intentos fallidos. Intenta de nuevo en {minutos_restantes} minuto(s)."

    clave_correcta = secrets.compare_digest(clave_ingresada, configuracion.CLAVE_MAESTRA_DESBLOQUEO)

    if not clave_correcta:
        suscripcion.intentos_fallidos += 1

        if suscripcion.intentos_fallidos >= configuracion.UMBRAL_INTENTOS_DESBLOQUEO:
            suscripcion.bloqueado_hasta = ahora + timedelta(
                minutes=configuracion.MINUTOS_BLOQUEO_INTENTOS_DESBLOQUEO
            )
            suscripcion.intentos_fallidos = 0

        db.commit()
        return False, "La contraseña de desbloqueo es incorrecta."

    suscripcion.fecha_inicio = ahora
    suscripcion.fecha_vencimiento = ahora + timedelta(days=configuracion.DIAS_SUSCRIPCION)
    suscripcion.intentos_fallidos = 0
    suscripcion.bloqueado_hasta = None
    suscripcion.fecha_ultimo_desbloqueo = ahora
    db.commit()

    return True, "Sistema desbloqueado correctamente. Suscripción renovada por un mes."


# =============================================================================
# CUENTAS DE PAGO DEL PROVEEDOR (solo lectura, configuración fija en código)
# =============================================================================

def listar_cuentas_proveedor() -> list[CuentaProveedorRespuesta]:
    """
    Devuelve las cuentas de pago definidas en cuentas_proveedor.py, resolviendo
    la URL pública del QR únicamente si el archivo realmente existe en disco
    en backend/imagenes/cuentas/. Si el proveedor olvidó copiar la imagen (o
    la cuenta no tiene QR), imagen_url queda en None y el frontend simplemente
    no dibuja la imagen para esa cuenta, sin romper el resto de la pantalla.
    """
    carpeta_cuentas = configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR
    resultado: list[CuentaProveedorRespuesta] = []

    for cuenta in CUENTAS_PROVEEDOR:
        imagen_url = None
        nombre_archivo = cuenta.get("archivo_imagen")

        if nombre_archivo:
            ruta_absoluta = os.path.join(carpeta_cuentas, nombre_archivo)
            if os.path.isfile(ruta_absoluta):
                imagen_url = f"/imagenes/cuentas/{nombre_archivo}"

        resultado.append(
            CuentaProveedorRespuesta(
                nombre=cuenta["nombre"],
                tipo_dato=cuenta["tipo_dato"],
                valor=cuenta["valor"],
                imagen_url=imagen_url,
            )
        )

    return resultado