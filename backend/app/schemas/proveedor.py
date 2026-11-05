# Ruta: backend/app/schemas/proveedor.py
# Esquemas de validación de datos para crear, actualizar y mostrar proveedores.

from pydantic import BaseModel, Field

from app.models.proveedor import CanalProveedor


class ProveedorBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    canal: CanalProveedor = CanalProveedor.OTRO
    notas: str | None = Field(default=None, max_length=255)


class ProveedorCrear(ProveedorBase):
    """Datos requeridos para registrar un nuevo proveedor."""
    pass


class ProveedorActualizar(BaseModel):
    """Datos opcionales para editar un proveedor existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = None
    canal: CanalProveedor | None = None
    notas: str | None = None


class ProveedorRespuesta(ProveedorBase):
    """Datos de proveedor que se devuelven al frontend."""
    id: int

    model_config = {"from_attributes": True}