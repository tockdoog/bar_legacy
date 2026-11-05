# Ruta: backend/app/schemas/compra.py
# Esquemas de validación de datos para registrar una compra a un proveedor
# (cabecera + lista de productos comprados) y para mostrarla en el frontend.

from datetime import datetime

from pydantic import BaseModel, Field


class ItemCompraCrear(BaseModel):
    """Datos de un producto dentro de una compra a registrar."""
    producto_id: int
    cantidad: int = Field(gt=0)
    costo_unitario: float = Field(ge=0)


class CompraCrear(BaseModel):
    """Datos completos para registrar una nueva compra a un proveedor."""
    proveedor_id: int
    items: list[ItemCompraCrear] = Field(min_length=1)


class DetalleCompraRespuesta(BaseModel):
    """Representa un producto dentro del detalle de una compra ya registrada."""
    id: int
    producto_id: int
    nombre_producto: str
    cantidad: int
    costo_unitario: float
    subtotal: float

    model_config = {"from_attributes": True}


class CompraRespuesta(BaseModel):
    """Representa una compra completa, con el nombre del proveedor y sus productos."""
    id: int
    proveedor_id: int
    nombre_proveedor: str
    fecha: datetime
    total: float
    detalles: list[DetalleCompraRespuesta] = []

    model_config = {"from_attributes": True}