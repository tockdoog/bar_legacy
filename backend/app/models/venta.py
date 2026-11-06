# Ruta: backend/app/models/venta.py
# Modelos de base de datos para las ventas del punto de venta (venta rápida o de
# mesa), el detalle de productos de cada venta, los pagos que componen el cobro
# (uno o varios métodos: factura partida) y la anulación de una venta ya cobrada.
#
# ZONA HORARIA: todas las fechas se guardan con ahora_colombia() (hora local de
# Colombia, sin zona), nunca con datetime.now(timezone.utc). Ver app/utils/zona_horaria.py.
#
# CAMBIO: se agregaron índices en las columnas que filtran los reportes y el
# historial (estado, fecha_pago, mesa_id, venta_id). PostgreSQL no indexa solo
# las llaves foráneas y, sin índices, las consultas se vuelven lentas al crecer los datos.

import enum

from sqlalchemy import Column, Integer, Float, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.finanzas import TipoImpuesto
from app.utils.zona_horaria import ahora_colombia


class EstadoVenta(str, enum.Enum):
    """Estados posibles del ciclo de vida de una venta."""
    ABIERTA = "abierta"      # Carrito en construcción, aún no se ha cobrado
    PAGADA = "pagada"        # Venta cobrada: ya descontó inventario
    CANCELADA = "cancelada"  # Carrito abierto anulado ANTES de cobrarse (no afectó inventario)
    ANULADA = "anulada"      # Venta que YA estaba cobrada y se anuló después (repone inventario)


class MetodoPago(str, enum.Enum):
    """
    Métodos de pago admitidos al cobrar. "MIXTO" no lo elige el cajero: el backend
    lo asigna cuando la venta se cobró con factura partida (más de un método); el
    detalle real vive en la tabla PagoVentaDetalle.
    """
    EFECTIVO = "efectivo"
    NEQUI = "nequi"
    DAVIPLATA = "daviplata"
    BANCOLOMBIA = "bancolombia"
    TARJETA_DEBITO = "tarjeta_debito"
    TARJETA_CREDITO = "tarjeta_credito"
    OTRO = "otro"
    MIXTO = "mixto"


# Etiquetas legibles en español para reportes (pantalla, Excel y PDF)
ETIQUETAS_METODO_PAGO = {
    MetodoPago.EFECTIVO: "Efectivo",
    MetodoPago.NEQUI: "Nequi",
    MetodoPago.DAVIPLATA: "Daviplata",
    MetodoPago.BANCOLOMBIA: "Bancolombia",
    MetodoPago.TARJETA_DEBITO: "Tarjeta débito",
    MetodoPago.TARJETA_CREDITO: "Tarjeta crédito",
    MetodoPago.OTRO: "Otro",
    MetodoPago.MIXTO: "Pago mixto",
}


class Venta(Base):
    """Tabla de ventas. Puede pertenecer a una mesa o ser una venta rápida (mesa_id nulo)."""
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    estado = Column(Enum(EstadoVenta), nullable=False, default=EstadoVenta.ABIERTA, index=True)

    # Montos en pesos colombianos (COP)
    subtotal = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)
    monto_pagado = Column(Float, nullable=True)
    cambio = Column(Float, nullable=True)

    # Método "resumen": el único método usado, o MIXTO si fue factura partida.
    # Queda nulo mientras la venta sigue abierta.
    metodo_pago = Column(Enum(MetodoPago), nullable=True)

    # Hora LOCAL de Colombia (sin zona)
    fecha_apertura = Column(DateTime, default=ahora_colombia)
    fecha_pago = Column(DateTime, nullable=True, index=True)

    # --- Auditoría de anulación de una venta YA cobrada ---
    # Los productos anulados siguen disponibles en "detalles" (no se borran).
    motivo_anulacion = Column(String, nullable=True)
    usuario_anulacion_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_anulacion = Column(DateTime, nullable=True, index=True)

    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")
    mesa = relationship("Mesa")
    pagos = relationship("PagoVentaDetalle", back_populates="venta", cascade="all, delete-orphan")

    # Dos columnas apuntan a "usuarios": cada relación indica explícitamente su llave foránea
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    usuario_anulacion = relationship("Usuario", foreign_keys=[usuario_anulacion_id])


class DetalleVenta(Base):
    """Cada fila es un producto del carrito de una venta, con precios e impuesto congelados."""
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)

    # Si el producto llegó como parte de una promoción, se guarda su id para agruparlo en pantalla
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=True)

    cantidad = Column(Integer, nullable=False, default=1)

    # Precios "congelados" al agregar el producto: cambios futuros no alteran ventas ya registradas
    precio_venta_unitario = Column(Float, nullable=False)
    precio_compra_unitario = Column(Float, nullable=False)

    # Impuesto "congelado" al momento de la venta (propio del producto o heredado de la
    # configuración global). Nulo solo en registros anteriores a este campo (se factura sin impuesto).
    tipo_impuesto_aplicado = Column(Enum(TipoImpuesto), nullable=True)
    porcentaje_impuesto_aplicado = Column(Float, nullable=True, default=0)
    etiqueta_impuesto_aplicado = Column(String(80), nullable=True)

    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto")
    promocion = relationship("Promocion")

    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_venta_unitario, 2)

    @property
    def ganancia(self) -> float:
        return round(self.cantidad * (self.precio_venta_unitario - self.precio_compra_unitario), 2)


class PagoVentaDetalle(Base):
    """
    Pago individual de una venta (factura partida). Una venta cobrada con un solo
    método tiene una fila; con efectivo y Nequi, por ejemplo, tiene dos.
    """
    __tablename__ = "pagos_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False, index=True)
    metodo_pago = Column(Enum(MetodoPago), nullable=False)
    monto = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="pagos")