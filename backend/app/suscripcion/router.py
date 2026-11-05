# Ruta: backend/app/suscripcion/router.py
# Endpoints HTTP del módulo de suscripción: consultar el estado del pago
# mensual, desbloquear el sistema con la contraseña maestra, y listar las
# cuentas de pago fijas del proveedor del software (de solo lectura).

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import configuracion
from app.database import obtener_db
from app.dependencies import obtener_usuario_actual, requerir_rol
from app.models.usuario import RolUsuario
from app.suscripcion.schemas import CuentaProveedorRespuesta, EstadoSuscripcion, SolicitudDesbloqueo
from app.suscripcion.service import (
    calcular_dias_restantes,
    esta_bloqueado,
    intentar_desbloqueo,
    listar_cuentas_proveedor,
    obtener_suscripcion,
)
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/suscripcion", tags=["Suscripción"])


def _construir_respuesta_estado(suscripcion, mensaje: str | None = None) -> EstadoSuscripcion:
    """Arma la respuesta de estado a partir del registro de suscripción actual."""
    dias_restantes = calcular_dias_restantes(suscripcion)
    bloqueado = esta_bloqueado(suscripcion)

    if mensaje is None:
        if bloqueado:
            mensaje = "El sistema está bloqueado por falta de pago. Realiza el pago y solicita el código de desbloqueo al proveedor."
        elif dias_restantes <= 1:
            mensaje = "Atención: falta 1 día para que el sistema se bloquee por falta de pago."

    return EstadoSuscripcion(
        dias_restantes=dias_restantes,
        bloqueado=bloqueado,
        fecha_vencimiento=suscripcion.fecha_vencimiento,
        valor_mensual_cop=configuracion.VALOR_SUSCRIPCION_MENSUAL,
        mensaje=mensaje,
    )


@router.get("/estado", response_model=EstadoSuscripcion)
def consultar_estado(db: Session = Depends(obtener_db)):
    """
    Devuelve días restantes, si el sistema está bloqueado y un mensaje de
    alerta. Esta ruta queda excluida del middleware de bloqueo en main.py,
    ya que el propio frontend la necesita para mostrar la pantalla de bloqueo.
    """
    suscripcion = obtener_suscripcion(db)
    return _construir_respuesta_estado(suscripcion)


@router.post("/desbloquear", response_model=EstadoSuscripcion)
@limitador.limit("5/minute")
def desbloquear_sistema(
    request: Request,
    solicitud: SolicitudDesbloqueo,
    db: Session = Depends(obtener_db),
    usuario_actual=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """
    Desbloquea el sistema ingresando la contraseña maestra de pago, entregada
    por el proveedor del software una vez confirma el pago. Solo el rol
    ADMINISTRADOR puede ejecutar esta acción, y está limitada a 5 intentos
    por minuto por IP (slowapi) para reforzar la protección contra fuerza bruta.
    """
    exito, mensaje = intentar_desbloqueo(db, solicitud.clave)

    if not exito:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=mensaje)

    suscripcion = obtener_suscripcion(db)
    return _construir_respuesta_estado(suscripcion, mensaje=mensaje)


@router.get("/cuentas-pago", response_model=list[CuentaProveedorRespuesta])
def obtener_cuentas_pago(usuario_actual=Depends(obtener_usuario_actual)):
    """
    Lista las cuentas de pago del proveedor del software (Nequi, Bancolombia,
    Nu, PayPal, etc.), para que el administrador del negocio sepa cómo pagar
    la suscripción. Es una configuración fija en código (cuentas_proveedor.py),
    no una tabla editable: no existen endpoints para crear, editar ni borrar
    estas cuentas. Requiere sesión activa (cualquier rol).
    """
    return listar_cuentas_proveedor()