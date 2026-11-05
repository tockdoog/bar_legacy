# Ruta: backend/app/models/venta.py
# Modelos de base de datos para las ventas registradas en el punto de venta
# (venta rápida o asociada a una mesa), el detalle de productos de cada venta,
# los pagos que componen el cobro (uno o varios métodos: factura partida), y
# la anulación de una venta ya cobrada (ej: el cliente pidió algo y luego se
# arrepintió después de que la factura ya se había generado).
#
# ZONA HORARIA: todas las fechas/horas de este modelo se guardan con
# ahora_colombia() (hora local de Colombia, "naive"), NUNCA con
# datetime.now(timezone.utc). Ver app/utils/zona_horaria.py para el detalle
# de por qué (SQLite no conserva tzinfo y mezclar UTC con hora local causaba
# que una venta apareciera fechada un día después en los reportes).

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
    CANCELADA = "cancelada"  # Carrito abierto que se anuló ANTES de cobrarse (no afectó inventario)
    ANULADA = "anulada"      # Venta que YA estaba cobrada y se anuló después (repone inventario)


class MetodoPago(str, enum.Enum):
    """
    Métodos de pago admitidos al cobrar una venta. No representa ningún nicho
    de negocio específico: son los medios de pago más comunes en Colombia.
    "MIXTO" no lo elige el cajero manualmente: el backend lo asigna solo
    cuando una venta se cobró con una factura partida (más de un método), y
    sirve como etiqueta resumen del campo Venta.metodo_pago; el detalle real
    de cuánto se pagó con cada método vive en la tabla PagoVentaDetalle.
    """
    EFECTIVO = "efectivo"
    NEQUI = "nequi"
    DAVIPLATA = "daviplata"
    BANCOLOMBIA = "bancolombia"
    TARJETA_DEBITO = "tarjeta_debito"
    TARJETA_CREDITO = "tarjeta_credito"
    OTRO = "otro"
    MIXTO = "mixto"


# Etiquetas legibles en español para mostrar el método de pago en reportes
# (pantalla, Excel y PDF), evitando exponer el valor crudo del enum (ej. "tarjeta_debito").
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
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    estado = Column(Enum(EstadoVenta), nullable=False, default=EstadoVenta.ABIERTA)

    subtotal = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)
    monto_pagado = Column(Float, nullable=True)
    cambio = Column(Float, nullable=True)

    # Método de pago "resumen": si la venta se cobró con un solo método, aquí
    # queda ese método (ej. EFECTIVO). Si se cobró con factura partida (dos o
    # más métodos), aquí queda MIXTO y el detalle exacto de cuánto correspondió
    # a cada método vive en la relación "pagos" (tabla pagos_venta). Queda nulo
    # mientras la venta sigue abierta (carrito en construcción).
    metodo_pago = Column(Enum(MetodoPago), nullable=True)

    # Se guarda la hora LOCAL de Colombia (naive), no UTC. Ver el bloque
    # "ZONA HORARIA" al inicio del archivo.
    fecha_apertura = Column(DateTime, default=ahora_colombia)
    fecha_pago = Column(DateTime, nullable=True)

    # --- Auditoría de anulación de una venta YA cobrada ---
    # Distinto del campo "estado=CANCELADA" (que es para carritos que nunca
    # llegaron a cobrarse). Aquí se registra el motivo, quién la anuló y cuándo,
    # para poder responder "quién borró esta venta y por qué" en caso de dudas.
    # Los PRODUCTOS anulados no necesitan un campo nuevo: siguen disponibles en
    # "detalles" (no se borran al anular, solo cambia venta.estado a ANULADA).
    motivo_anulacion = Column(String, nullable=True)
    usuario_anulacion_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_anulacion = Column(DateTime, nullable=True)

    # Relación con los productos incluidos en esta venta
    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")
    mesa = relationship("Mesa")

    # Relación con el detalle de pagos (factura partida): una venta puede
    # tener uno o varios registros aquí, uno por cada método usado al cobrar.
    pagos = relationship("PagoVentaDetalle", back_populates="venta", cascade="all, delete-orphan")

    # IMPORTANTE: como existen DOS columnas que apuntan a la tabla "usuarios"
    # (usuario_id = quien vendió, usuario_anulacion_id = quien anuló),
    # SQLAlchemy no puede adivinar sola cuál FK usar en cada relación; por eso
    # ambas relaciones indican explícitamente su columna con foreign_keys.
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    usuario_anulacion = relationship("Usuario", foreign_keys=[usuario_anulacion_id])


class DetalleVenta(Base):
    """Cada fila representa un producto agregado al carrito de una venta, con precios congelados."""
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)

    # Si este producto llegó al carrito como parte de una promoción, se guarda su id
    # para poder mostrarlo agrupado en el frontend (ej: "Cerveza (Promo: 2x1 + snack)")
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=True)

    cantidad = Column(Integer, nullable=False, default=1)

    # Precios "congelados" al momento de agregar el producto, para que cambios futuros
    # en el inventario no alteren ventas ya registradas ni el cálculo de ganancia.
    precio_venta_unitario = Column(Float, nullable=False)
    precio_compra_unitario = Column(Float, nullable=False)

    # --- Impuesto "congelado" al momento de la venta (Análisis Financiero) ---
    # Se guarda qué impuesto aplicaba a este producto EN ESE MOMENTO (propio
    # del producto, o heredado de la configuración global), para que la
    # factura de una venta antigua nunca cambie si más adelante se edita el
    # impuesto del producto o la configuración global. Quedan nulos/en cero
    # solo en registros creados ANTES de este campo (se tratan como "sin
    # impuesto" al facturar, ver generador_factura.py).
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
    Detalle de cada pago individual de una venta (factura partida). Una venta
    cobrada con un solo método tiene una única fila aquí; una venta cobrada
    con, por ejemplo, la mitad en efectivo y la mitad en Nequi, tiene DOS
    filas: una por cada método con su monto correspondiente. Esta tabla es
    nueva (no una columna agregada a una tabla existente), por lo que
    SQLAlchemy la crea sola al iniciar el backend (create_all), sin requerir
    ninguna migración manual sobre bases de datos ya existentes.
    """
    __tablename__ = "pagos_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    metodo_pago = Column(Enum(MetodoPago), nullable=False)
    monto = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="pagos")