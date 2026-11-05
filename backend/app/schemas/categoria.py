# Ruta: backend/app/schemas/categoria.py
# Esquemas de validación de datos para las categorías de productos.

from pydantic import BaseModel, Field


class CategoriaBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)


class CategoriaCrear(CategoriaBase):
    """Datos requeridos para registrar una nueva categoría."""
    pass


class CategoriaActualizar(BaseModel):
    """Datos opcionales para editar una categoría existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)


class CategoriaRespuesta(CategoriaBase):
    """Datos de categoría que se devuelven al frontend."""
    id: int

    model_config = {"from_attributes": True}