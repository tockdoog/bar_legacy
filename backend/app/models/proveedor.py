# Ruta: backend/app/models/proveedor.py
# Modelo de base de datos para los proveedores que surten productos al negocio.

import enum

from sqlalchemy import Column, Integer, String, Enum

from app.database import Base


class CanalProveedor(str, enum.Enum):
    """Medio por el cual se hacen los pedidos a este proveedor."""
    RAPPI = "rappi"
    DIDI = "didi"
    LLAMADA = "llamada"
    DISTRIBUIDOR = "distribuidor"
    OTRO = "otro"


class Proveedor(Base):
    """Tabla de proveedores registrados para realizar pedidos de compra."""
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    telefono = Column(String(30), nullable=True)
    canal = Column(Enum(CanalProveedor), nullable=False, default=CanalProveedor.OTRO)
    notas = Column(String(255), nullable=True)