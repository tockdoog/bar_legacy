# Ruta: backend/app/models/categoria.py
# Modelo de base de datos para las categorías que agrupan los productos del inventario.

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Categoria(Base):
    """Tabla de categorías genéricas para clasificar productos (ej: bebidas, snacks, otros)."""
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(80), unique=True, nullable=False)
    descripcion = Column(String(255), nullable=True)

    # Relación uno a muchos: una categoría puede tener muchos productos
    productos = relationship("Producto", back_populates="categoria")