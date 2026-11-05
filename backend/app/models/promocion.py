# Ruta: backend/app/models/promocion.py
# Modelos de base de datos para las promociones (combos de productos vendidos a
# un precio especial), por ejemplo "2 cervezas + snack" o "six pack promocional".

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Promocion(Base):
    """Tabla de promociones disponibles para la venta."""
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(String(255), nullable=True)
    precio_promocional = Column(Float, nullable=False)
    activa = Column(Boolean, default=True, nullable=False)

    componentes = relationship("ComponentePromocion", back_populates="promocion", cascade="all, delete-orphan")


class ComponentePromocion(Base):
    """Cada fila representa un producto (y su cantidad) que forma parte de una promoción."""
    __tablename__ = "componentes_promocion"

    id = Column(Integer, primary_key=True, index=True)
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)

    promocion = relationship("Promocion", back_populates="componentes")
    producto = relationship("Producto")