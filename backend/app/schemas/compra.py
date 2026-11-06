# Ruta: backend/app/models/compra.py
# Modelos de base de datos para los pedidos de compra a proveedores. Al registrar una
# compra, el inventario de cada producto involucrado aumenta automáticamente.
#
# ZONA HORARIA: la fecha de la compra se guarda con ahora_colombia() (hora local de
# Colombia, sin zona), igual que las ventas.
#
# CAMBIO: índices en "fecha" (la filtran los reportes y el resumen financiero) y en las
# llaves foráneas "compra_id" y "proveedor_id". PostgreSQL no indexa solo las llaves
# foráneas y, sin índices, las consultas se vuelven lentas al crecer el historial.

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class Compra(Base):
    """Tabla de compras registradas a un proveedor (cabecera de la compra)."""
    __tablename__ = "compras"

    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    fecha = Column(DateTime, default=ahora_colombia, index=True)
    total = Column(Float, nullable=False, default=0)  # Pesos colombianos (COP)

    detalles = relationship("DetalleCompra", back_populates="compra", cascade="all, delete-orphan")
    proveedor = relationship("Proveedor")


class DetalleCompra(Base):
    """Cada fila representa un producto incluido dentro de una compra a proveedor."""
    __tablename__ = "detalles_compra"

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)

    cantidad = Column(Integer, nullable=False)
    costo_unitario = Column(Float, nullable=False)

    compra = relationship("Compra", back_populates="detalles")
    producto = relationship("Producto")

    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.costo_unitario, 2)