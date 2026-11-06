# Ruta: backend/app/schemas/proveedor.py
# Esquemas de validación de datos para crear, actualizar y mostrar proveedores.
#
# CORRECCIONES (PostgreSQL/Neon):
# - "telefono" y "notas" tienen largo máximo también al editar (columnas de 30 y 255).
# - Un null explícito en "nombre" o "canal" se rechaza con 422 (violaba NOT NULL, error 500).
# - El nombre se limpia de espacios; teléfono y notas vacíos se guardan como nulos.

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.proveedor import CanalProveedor

# Campos del proveedor que en la base de datos no admiten nulo
CAMPOS_PROVEEDOR_NO_NULOS = ("nombre", "canal")


def _limpiar(valor):
    """Quita espacios de los bordes de un texto antes de validar su largo."""
    return valor.strip() if isinstance(valor, str) else valor


def _vacio_a_nulo(valor):
    """Convierte un texto vacío (o solo espacios) en None."""
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


class ProveedorBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    canal: CanalProveedor = CanalProveedor.OTRO
    notas: str | None = Field(default=None, max_length=255)


class ProveedorCrear(ProveedorBase):
    """Datos requeridos para registrar un nuevo proveedor."""

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("telefono", "notas", mode="before")
    @classmethod
    def limpiar_opcionales(cls, valor):
        return _vacio_a_nulo(valor)


class ProveedorActualizar(BaseModel):
    """Datos opcionales para editar un proveedor existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    canal: CanalProveedor | None = None
    notas: str | None = Field(default=None, max_length=255)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("telefono", "notas", mode="before")
    @classmethod
    def limpiar_opcionales(cls, valor):
        return _vacio_a_nulo(valor)

    @model_validator(mode="after")
    def _rechazar_nulos_explicitos(self) -> "ProveedorActualizar":
        # Omitir un campo es válido (no se cambia); enviarlo como null en uno obligatorio no.
        for campo in CAMPOS_PROVEEDOR_NO_NULOS:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo.")
        return self


class ProveedorRespuesta(ProveedorBase):
    """Datos de proveedor que se devuelven al frontend."""
    id: int

    model_config = {"from_attributes": True}