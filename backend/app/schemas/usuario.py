# Ruta: backend/app/schemas/usuario.py
# Esquemas de validación de datos para crear, actualizar, mostrar y gestionar
# la contraseña y los permisos de los usuarios del sistema.

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.usuario import RolUsuario
from app.permisos import es_permiso_valido


def _validar_fortaleza(valor: str) -> str:
    """Exige mayúscula, minúscula y número como mínimo, evitando contraseñas débiles."""
    if not re.search(r"[A-Z]", valor):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula")
    if not re.search(r"[a-z]", valor):
        raise ValueError("La contraseña debe incluir al menos una letra minúscula")
    if not re.search(r"[0-9]", valor):
        raise ValueError("La contraseña debe incluir al menos un número")
    return valor


def _validar_permisos_lista(valor: list[str]) -> list[str]:
    """Verifica que cada clave de permiso recibida exista en el catálogo del sistema."""
    invalidos = [clave for clave in valor if not es_permiso_valido(clave)]
    if invalidos:
        raise ValueError(f"Permiso(s) inválido(s): {', '.join(invalidos)}")
    return valor


class UsuarioBase(BaseModel):
    """Campos comunes compartidos entre los diferentes esquemas de usuario."""
    nombre_completo: str = Field(min_length=3, max_length=120)
    nombre_usuario: str = Field(min_length=3, max_length=50)
    correo: EmailStr
    rol: RolUsuario = RolUsuario.EMPLEADO


class UsuarioCrear(UsuarioBase):
    """
    Datos requeridos para crear un nuevo usuario (solo accesible por el
    administrador). El campo 'permisos' solo tiene efecto cuando rol es
    EMPLEADO; si se crea un administrador, el router ignora lo que llegue
    aquí porque su rol ya otorga acceso completo.
    """
    contrasena: str = Field(min_length=8, max_length=72)
    permisos: list[str] = Field(default_factory=list)

    @field_validator("contrasena")
    @classmethod
    def validar_fortaleza_contrasena(cls, valor: str) -> str:
        return _validar_fortaleza(valor)

    @field_validator("permisos")
    @classmethod
    def validar_permisos(cls, valor: list[str]) -> list[str]:
        return _validar_permisos_lista(valor)


class UsuarioActualizar(BaseModel):
    """Datos opcionales para que el administrador edite un usuario existente."""
    nombre_completo: str | None = Field(default=None, min_length=3, max_length=120)
    correo: EmailStr | None = None
    rol: RolUsuario | None = None
    activo: bool | None = None
    permisos: list[str] | None = None

    @field_validator("permisos")
    @classmethod
    def validar_permisos(cls, valor: list[str] | None) -> list[str] | None:
        if valor is None:
            return valor
        return _validar_permisos_lista(valor)


class CambioContrasenaPropia(BaseModel):
    """Datos para que un usuario cambie su propia contraseña (requiere la actual)."""
    contrasena_actual: str
    contrasena_nueva: str = Field(min_length=8, max_length=72)

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_fortaleza_contrasena(cls, valor: str) -> str:
        return _validar_fortaleza(valor)


class RestablecerContrasena(BaseModel):
    """Datos para que el administrador restablezca la contraseña de otro usuario."""
    contrasena_nueva: str = Field(min_length=8, max_length=72)

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_fortaleza_contrasena(cls, valor: str) -> str:
        return _validar_fortaleza(valor)


class UsuarioRespuesta(UsuarioBase):
    """Datos de usuario que se exponen al frontend (nunca incluye la contraseña)."""
    id: int
    activo: bool
    # 'validation_alias' lee la propiedad Python 'permisos_lista' del modelo
    # ORM (lista ya convertida), no la columna cruda 'permisos' (texto con
    # comas), que es un detalle interno de almacenamiento.
    permisos: list[str] = Field(default_factory=list, validation_alias="permisos_lista")

    model_config = {"from_attributes": True, "populate_by_name": True}


class PermisoDisponible(BaseModel):
    """Un permiso del catálogo del sistema, para que el frontend arme la lista de checkboxes."""
    clave: str
    descripcion: str