# Ruta: backend/app/schemas/venta.py
# Esquemas de validación de datos para el flujo completo de una venta: apertura del
# carrito, agregar/quitar productos, promociones (combos), cobro (uno o varios métodos
# de pago: factura partida), anulación de una venta ya cobrada (con motivo obligatorio)
# y envío de la factura por correo electrónico. Montos en pesos colombianos (COP).
#
# CORRECCIONES (PostgreSQL/Neon):
# - Cantidades y montos con tope: sin él, un entero mayor a 2.147 millones desborda la
#   columna Integer (error 500) y un monto "Infinity" pasaba la validación "mayor a 0".
# - El motivo de anulación se limpia de espacios antes de validar el largo mínimo.

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.venta import EstadoVenta, MetodoPago

# Topes razonables para un punto de venta (evitan desbordes en la base de datos)
CANTIDAD_MAXIMA_ITEM = 10_000
CANTIDAD_MAXIMA_PROMOCION = 1_000
MONTO_MAXIMO_PAGO = 100_000_000_000  # Cien mil millones de pesos


# --- Bloque: apertura de venta ---
class VentaCrear(BaseModel):
    """Datos para abrir una nueva venta. Si no se indica mesa_id, es una venta rápida."""
    mesa_id: int | None = None


# --- Bloque: agregar/actualizar productos individuales en el carrito ---
class ItemVentaCrear(BaseModel):
    """Datos para agregar un producto al carrito de una venta abierta."""
    producto_id: int
    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA_ITEM)


class ItemVentaActualizar(BaseModel):
    """Datos para modificar la cantidad de un producto ya agregado al carrito."""
    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA_ITEM)


# --- Bloque: agregar una promoción (combo de productos) al carrito ---
class PromocionVentaCrear(BaseModel):
    """
    Datos para agregar una promoción al carrito. "cantidad" es la cantidad de VECES que
    se agrega el combo completo: el router multiplica esta cantidad por la de cada
    producto componente.
    """
    promocion_id: int
    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA_PROMOCION)


# --- Bloque: cobro de la venta (soporta factura partida: varios métodos) ---
class PagoParcial(BaseModel):
    """
    Un pago dentro del cobro de una venta. Con un solo método se envía una lista con
    un PagoParcial; con factura partida (ej. mitad efectivo, mitad Nequi), dos o más.
    """
    metodo_pago: MetodoPago
    monto: float = Field(gt=0, le=MONTO_MAXIMO_PAGO)


class PagoVenta(BaseModel):
    """
    Datos para cobrar una venta abierta. "pagos" es la lista de métodos usados. Pydantic
    valida que cada método esté en el enum MetodoPago y que cada monto sea positivo y
    razonable. Que la suma cubra el total se valida en el router, porque depende de la venta.
    """
    pagos: list[PagoParcial] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def _validar_pagos_no_vacios(self) -> "PagoVenta":
        # Refuerzo: la lista no debe llegar vacía aunque un cliente HTTP ignore las restricciones del campo
        if not self.pagos:
            raise ValueError("Debes indicar al menos un método de pago con su monto.")
        return self


# --- Bloque: anulación de una venta ya cobrada ---
class VentaAnular(BaseModel):
    """
    Datos para anular una venta YA cobrada. El motivo es obligatorio (mínimo 3 caracteres
    sin contar espacios de los bordes) para dejar trazabilidad. El usuario que anula se
    toma de la sesión autenticada y los productos, de los detalles ya guardados.
    """
    motivo: str = Field(min_length=3, max_length=300)

    @field_validator("motivo", mode="before")
    @classmethod
    def _limpiar_motivo(cls, valor):
        """Quita espacios de los bordes ANTES de validar el largo mínimo."""
        return valor.strip() if isinstance(valor, str) else valor


# --- Bloque: envío de la factura de una venta ya cobrada por correo ---
class FacturaEnviarCorreo(BaseModel):
    """
    Datos para enviar la factura al correo del cliente. EmailStr rechaza con un 422 todo
    texto que no sea un correo válido, antes de intentar el envío por SMTP.
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
    Venta completa, con sus productos, totales, el desglose de pagos y, si aplica, los
    datos de auditoría de su anulación. Los productos anulados se consultan en "detalles"
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