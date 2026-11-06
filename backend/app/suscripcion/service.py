# Ruta: backend/app/suscripcion/service.py
# Lógica de negocio del módulo de suscripción: obtener/crear el registro de pago,
# calcular días restantes, determinar si el sistema debe bloquearse, procesar los
# intentos de desbloqueo con protección contra fuerza bruta y listar las cuentas
# de pago fijas del proveedor (definidas en cuentas_proveedor.py).
#
# CAMBIOS: todas las fechas usan la hora local de Colombia sin zona (ahora_colombia),
# como el resto del sistema. Los registros ya guardados en UTC quedan desplazados
# 5 horas hacia adelante la primera vez (la suscripción vence 5 h más tarde); no
# afecta el funcionamiento. Se tolera la creación simultánea del registro único
# (varias instancias arrancando a la vez) y las rutas son absolutas.

import math
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import configuracion
from app.suscripcion.cuentas_proveedor import CUENTAS_PROVEEDOR
from app.suscripcion.models import Suscripcion
from app.suscripcion.schemas import CuentaProveedorRespuesta
from app.utils.rutas import ruta_absoluta
from app.utils.zona_horaria import ZONA_HORARIA_COLOMBIA, ahora_colombia

# Identificador fijo: solo existe un registro de suscripción para todo el sistema
ID_SUSCRIPCION_UNICA = 1


def _a_hora_colombia(fecha: datetime) -> datetime:
    """Devuelve la fecha sin zona en hora de Colombia (si llegara con zona, la convierte)."""
    if fecha.tzinfo is not None:
        return fecha.astimezone(ZONA_HORARIA_COLOMBIA).replace(tzinfo=None)
    return fecha


def obtener_suscripcion(db: Session) -> Suscripcion:
    """
    Devuelve el registro único de suscripción. Si es la primera vez que arranca el
    sistema, lo crea con un ciclo que inicia hoy. Si otra instancia lo creó al mismo
    tiempo, se descarta el intento propio y se lee el existente.
    """
    suscripcion = db.query(Suscripcion).filter(Suscripcion.id == ID_SUSCRIPCION_UNICA).first()
    if suscripcion is not None:
        return suscripcion

    ahora = ahora_colombia()
    nueva = Suscripcion(
        id=ID_SUSCRIPCION_UNICA,
        fecha_inicio=ahora,
        fecha_vencimiento=ahora + timedelta(days=configuracion.DIAS_SUSCRIPCION),
    )
    db.add(nueva)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(Suscripcion).filter(Suscripcion.id == ID_SUSCRIPCION_UNICA).one()
    db.refresh(nueva)
    return nueva


def calcular_dias_restantes(suscripcion: Suscripcion) -> int:
    """Calcula cuántos días completos faltan para el vencimiento (0 si ya venció)."""
    segundos = (_a_hora_colombia(suscripcion.fecha_vencimiento) - ahora_colombia()).total_seconds()
    if segundos <= 0:
        return 0
    return math.ceil(segundos / 86400)


def esta_bloqueado(suscripcion: Suscripcion) -> bool:
    """El sistema se bloquea automáticamente en el instante en que vence la suscripción."""
    return ahora_colombia() >= _a_hora_colombia(suscripcion.fecha_vencimiento)


def intentar_desbloqueo(db: Session, clave_ingresada: str) -> tuple[bool, str]:
    """
    Valida la clave maestra de desbloqueo (entregada por el proveedor tras el pago)
    y, si es correcta, renueva el ciclo por un mes más desde este momento.

    Seguridad: comparación con secrets.compare_digest (sin ataques de temporización),
    bloqueo temporal tras varios intentos fallidos y la clave nunca se registra.
    """
    suscripcion = obtener_suscripcion(db)
    ahora = ahora_colombia()

    if suscripcion.bloqueado_hasta and ahora < _a_hora_colombia(suscripcion.bloqueado_hasta):
        minutos = math.ceil((_a_hora_colombia(suscripcion.bloqueado_hasta) - ahora).total_seconds() / 60)
        return False, f"Demasiados intentos fallidos. Intenta de nuevo en {minutos} minuto(s)."

    # compare_digest necesita bytes para aceptar caracteres no ASCII sin lanzar TypeError
    clave_correcta = secrets.compare_digest(
        clave_ingresada.encode("utf-8"), configuracion.CLAVE_MAESTRA_DESBLOQUEO.encode("utf-8")
    )

    if not clave_correcta:
        suscripcion.intentos_fallidos += 1
        if suscripcion.intentos_fallidos >= configuracion.UMBRAL_INTENTOS_DESBLOQUEO:
            suscripcion.bloqueado_hasta = ahora + timedelta(minutes=configuracion.MINUTOS_BLOQUEO_INTENTOS_DESBLOQUEO)
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
    Devuelve las cuentas de pago de cuentas_proveedor.py, resolviendo la URL
    pública del QR solo si el archivo existe en backend/imagenes/cuentas/.
    """
    carpeta_cuentas = ruta_absoluta(configuracion.CARPETA_IMAGENES_CUENTAS_PROVEEDOR)
    resultado: list[CuentaProveedorRespuesta] = []

    for cuenta in CUENTAS_PROVEEDOR:
        imagen_url = None
        nombre_archivo = cuenta.get("archivo_imagen")
        if nombre_archivo and os.path.isfile(os.path.join(carpeta_cuentas, nombre_archivo)):
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