# Ruta: backend/app/suscripcion/schemas.py
# Esquemas Pydantic usados por el router de suscripción para validar entradas
# y estructurar las respuestas de la API: el estado del ciclo de pago
# mensual, el desbloqueo con la clave maestra, y las cuentas de pago fijas
# del proveedor del software (solo lectura, nunca se crean/editan por API).

from datetime import datetime

from pydantic import BaseModel, Field


class EstadoSuscripcion(BaseModel):
    """Respuesta que informa al frontend el estado actual del pago mensual."""
    dias_restantes: int
    bloqueado: bool
    fecha_vencimiento: datetime
    valor_mensual_cop: int
    mensaje: str | None = None


class SolicitudDesbloqueo(BaseModel):
    """Cuerpo esperado al intentar desbloquear el sistema con la clave maestra."""
    clave: str = Field(..., min_length=1, max_length=255)


class CuentaProveedorRespuesta(BaseModel):
    """
    Una cuenta/medio de pago del proveedor del software, tal como se muestra
    al administrador del negocio en la pantalla de bloqueo y en el aviso de
    vencimiento próximo. Es de solo lectura: no existe forma de crear,
    editar ni eliminar estas cuentas desde la API.
    """
    nombre: str
    tipo_dato: str
    valor: str
    imagen_url: str | None = None