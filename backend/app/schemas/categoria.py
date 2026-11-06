# Ruta: backend/app/schemas/categoria.py
# Esquemas de validación de datos para las categorías de productos.
#
# CORRECCIÓN: el nombre se limpia de espacios antes de validar (antes " Bebidas" y
# "Bebidas" contaban como categorías distintas) y una descripción vacía se guarda como nula.

from pydantic import BaseModel, Field, field_validator


def _limpiar(valor):
    """Quita espacios de los bordes de un texto antes de validar su largo."""
    return valor.strip() if isinstance(valor, str) else valor


def _vacio_a_nulo(valor):
    """Convierte un texto vacío (o solo espacios) en None."""
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


class CategoriaBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)


class CategoriaCrear(CategoriaBase):
    """Datos requeridos para registrar una nueva categoría."""

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("descripcion", mode="before")
    @classmethod
    def limpiar_descripcion(cls, valor):
        return _vacio_a_nulo(valor)


class CategoriaActualizar(BaseModel):
    """Datos opcionales para editar una categoría existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("descripcion", mode="before")
    @classmethod
    def limpiar_descripcion(cls, valor):
        return _vacio_a_nulo(valor)


class CategoriaRespuesta(CategoriaBase):
    """Datos de categoría que se devuelven al frontend."""
    id: int

    model_config = {"from_attributes": True}