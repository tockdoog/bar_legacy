# Ruta: backend/app/schemas/venta.py
# Esquemas de validación de datos para el flujo completo de una venta:
# apertura del carrito, agregar/quitar productos, agregar promociones (combos),
# cobro (con uno o varios métodos de pago: factura partida), anulación
# posterior de una venta ya cobrada (con motivo obligatorio) y envío de la
# factura por correo electrónico.

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.venta import EstadoVenta, MetodoPago


# --- Bloque: apertura de venta ---
class VentaCrear(BaseModel):
    """Datos para abrir una nueva venta. Si no se indica mesa_id, es una venta rápida."""
    mesa_id: int | None = None


# --- Bloque: agregar/actualizar productos individuales en el carrito ---
class ItemVentaCrear(BaseModel):
    """Datos para agregar un producto al carrito de una venta abierta."""
    producto_id: int
    cantidad: int = Field(gt=0)


class ItemVentaActualizar(BaseModel):
    """Datos para modificar la cantidad de un producto ya agregado al carrito."""
    cantidad: int = Field(gt=0)


# --- Bloque: agregar una promoción (combo de productos) al carrito ---
class PromocionVentaCrear(BaseModel):
    """
    Datos para agregar una promoción (combo de productos) al carrito de una
    venta abierta. "cantidad" es la cantidad de VECES que se agrega el combo
    completo (no de un producto individual): el router (ventas.py) multiplica
    esta cantidad por la cantidad de cada producto componente de la promoción.
    """
    promocion_id: int
    cantidad: int = Field(gt=0)


# --- Bloque: cobro de la venta (soporta factura partida: varios métodos) ---
class PagoParcial(BaseModel):
    """
    Un único pago dentro del cobro de una venta. Una venta con un solo método
    de pago envía una lista con un solo PagoParcial; una factura partida (ej.
    mitad efectivo, mitad Nequi) envía dos o más.
    """
    metodo_pago: MetodoPago
    monto: float = Field(gt=0)


class PagoVenta(BaseModel):
    """
    Datos para cobrar una venta abierta. "pagos" es la lista de métodos de
    pago usados (uno o varios, para soportar factura partida). Pydantic valida
    automáticamente que cada método esté dentro del enum MetodoPago y que
    cada monto sea positivo, rechazando cualquier valor fuera de esas reglas
    con un error 422 antes de que el dato llegue a la base de datos.
    La suma de todos los montos debe cubrir el total de la venta; esa
    validación puntual (que depende del total de la venta, no solo de la
    forma del dato) se hace en el router, no aquí.
    """
    pagos: list[PagoParcial] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _validar_pagos_no_vacios(self) -> "PagoVenta":
        # Refuerzo adicional: cada pago individual ya exige monto > 0 (arriba),
        # pero se valida aquí también que la lista no llegue vacía por algún
        # cliente HTTP que ignore las restricciones de Pydantic del campo.
        if not self.pagos:
            raise ValueError("Debes indicar al menos un método de pago con su monto.")
        return self


# --- Bloque: anulación de una venta ya cobrada ---
class VentaAnular(BaseModel):
    """
    Datos para anular una venta que YA estaba cobrada. El motivo es
    obligatorio (mínimo 3 caracteres) para dejar trazabilidad de por qué se
    anuló, junto con el usuario que la anula (se toma de la sesión
    autenticada, no de este esquema, para que no se pueda falsificar). Los
    productos anulados no se piden aquí: se toman automáticamente de los
    detalles ya guardados de la venta (nunca se borran al anular).
    """
    motivo: str = Field(min_length=3, max_length=300)


# --- Bloque: envío de la factura de una venta ya cobrada por correo ---
class FacturaEnviarCorreo(BaseModel):
    """
    Datos para enviar la factura de una venta ya cobrada al correo del
    cliente. Pydantic valida automáticamente que "correo" tenga un formato
    de correo electrónico válido (EmailStr), rechazando cualquier texto que
    no lo sea con un error 422 antes de intentar el envío por SMTP.
    """
    correo: EmailStr


# --- Bloque: respuesta de un producto dentro del carrito de una venta ---
class DetalleVentaRespuesta(BaseModel):
    """Representa un producto dentro del carrito de una venta."""
    id: int
    producto_id: int
    nombre_producto: str
    promocion_id: int | None = None
    nombre_promocion: str | None = None
    cantidad: int
    precio_venta_unitario: float
    subtotal: float

    model_config = {"from_attributes": True}


# --- Bloque: respuesta del detalle de un pago (factura partida) ---
class PagoDetalleRespuesta(BaseModel):
    """Representa un pago individual dentro del cobro de una venta."""
    metodo_pago: MetodoPago
    monto: float

    model_config = {"from_attributes": True}


# --- Bloque: respuesta completa de una venta ---
class VentaRespuesta(BaseModel):
    """
    Representa una venta completa, con sus productos, totales, el desglose de
    pagos (uno o varios métodos) y, si aplica, los datos de auditoría de su
    anulación. Los productos anulados se consultan a través de "detalles"
    (no se borran al anular la venta).
    """
    id: int
    mesa_id: int | None
    estado: EstadoVenta
    subtotal: float
    total: float
    monto_pagado: float | None
    cambio: float | None
    metodo_pago: MetodoPago | None = None
    pagos: list[PagoDetalleRespuesta] = []
    fecha_apertura: datetime
    fecha_pago: datetime | None
    detalles: list[DetalleVentaRespuesta] = []

    nombre_vendedor: str | None = None
    numero_mesa: str | None = None

    motivo_anulacion: str | None = None
    nombre_usuario_anulacion: str | None = None
    fecha_anulacion: datetime | None = None

    model_config = {"from_attributes": True}