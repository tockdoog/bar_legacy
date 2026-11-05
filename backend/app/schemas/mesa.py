# Ruta: backend/app/schemas/mesa.py
# Esquemas de validación de datos para crear, actualizar y mostrar mesas.

from pydantic import BaseModel, Field

from app.models.mesa import EstadoMesa


class MesaCrear(BaseModel):
    """Datos requeridos para registrar una nueva mesa."""
    numero: str = Field(min_length=1, max_length=20)


class MesaActualizar(BaseModel):
    """Datos opcionales para editar una mesa existente."""
    numero: str | None = Field(default=None, min_length=1, max_length=20)
    estado: EstadoMesa | None = None


class MesaRespuesta(BaseModel):
    """Datos de una mesa, incluyendo el id de su venta abierta si la tiene."""
    id: int
    numero: str
    estado: EstadoMesa
    venta_abierta_id: int | None = None

    model_config = {"from_attributes": True}