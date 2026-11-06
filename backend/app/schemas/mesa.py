# Ruta: backend/app/schemas/mesa.py
# Esquemas de validación de datos para crear, actualizar y mostrar mesas, y para
# informar qué usuario tiene bloqueada una mesa.

from datetime import datetime

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


class BloqueoMesaRespuesta(BaseModel):
    """Quién está atendiendo una mesa. "es_mio" lo calcula el servidor para quien consulta."""
    mesa_id: int
    usuario_id: int
    nombre_completo: str
    nombre_usuario: str
    desde: datetime
    es_mio: bool