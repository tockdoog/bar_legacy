# Ruta: backend/app/models/mesa.py
# Modelo de base de datos para las mesas del negocio y su estado actual.

import enum

from sqlalchemy import Column, Integer, String, Enum

from app.database import Base


class EstadoMesa(str, enum.Enum):
    """Estados posibles de una mesa dentro del punto de venta."""
    LIBRE = "libre"
    OCUPADA = "ocupada"
    PENDIENTE_PAGO = "pendiente_pago"


class Mesa(Base):
    """Tabla de mesas físicas del negocio, usadas en el módulo de punto de venta."""
    __tablename__ = "mesas"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(20), unique=True, nullable=False)
    estado = Column(Enum(EstadoMesa), nullable=False, default=EstadoMesa.LIBRE)