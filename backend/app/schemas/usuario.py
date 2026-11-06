# Ruta: backend/app/schemas/usuario.py
# Esquemas de validación para crear, actualizar, mostrar y gestionar la contraseña y
# los permisos de los usuarios del sistema.
#
# CORRECCIONES:
# - bcrypt solo admite 72 BYTES, no 72 caracteres: una contraseña con tildes o "ñ"
#   pasaba la validación de largo y luego fallaba con error 500. Ahora se valida en bytes.
# - El nombre de usuario al crear solo admite letras, números, punto, guion y guion bajo.
# - Un null explícito en un campo obligatorio al editar se rechaza con 422.
# - La contraseña actual tiene un largo máximo (evita gastar CPU con textos enormes).

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.usuario import RolUsuario
from app.permisos import es_permiso_valido
from app.security import LIMITE_BYTES_CONTRASENA

# Campos del usuario que en la base de datos no admiten nulo
CAMPOS_USUARIO_NO_NULOS = ("nombre_completo", "correo", "rol", "activo")


def _validar_fortaleza(valor: str) -> str:
    """Exige un largo seguro en bytes, y mayúscula, minúscula y número como mínimo."""
    if len(valor.encode("utf-8")) > LIMITE_BYTES_CONTRASENA:
        raise ValueError(
            f"La contraseña no puede superar los {LIMITE_BYTES_CONTRASENA} bytes "
            "(las tildes y la ñ ocupan más de un byte)."
        )
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


def _limpiar_texto(valor):
    """Quita espacios de los bordes antes de validar el largo mínimo."""
    return valor.strip() if isinstance(valor, str) else valor


class UsuarioBase(BaseModel):
    """Campos comunes compartidos entre los diferentes esquemas de usuario."""
    nombre_completo: str = Field(min_length=3, max_length=120)
    nombre_usuario: str = Field(min_length=3, max_length=50)
    correo: EmailStr
    rol: RolUsuario = RolUsuario.EMPLEADO


class UsuarioCrear(UsuarioBase):
    """
    Datos para crear un usuario (solo el administrador). "permisos" solo tiene efecto con
    rol EMPLEADO; si se crea un administrador, el router lo ignora porque su rol ya da
    acceso completo.
    """
    # Se redeclara aquí (y no en UsuarioBase) para no exigir el formato a usuarios antiguos al mostrarlos
    nombre_usuario: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    contrasena: str = Field(min_length=8, max_length=72)
    permisos: list[str] = Field(default_factory=list)

    @field_validator("nombre_completo", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar_texto(valor)

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

    @field_validator("nombre_completo", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar_texto(valor)

    @field_validator("permisos")
    @classmethod
    def validar_permisos(cls, valor: list[str] | None) -> list[str] | None:
        if valor is None:
            return valor
        return _validar_permisos_lista(valor)

    @model_validator(mode="after")
    def _rechazar_nulos_explicitos(self) -> "UsuarioActualizar":
        # Omitir un campo es válido (no se cambia); enviarlo como null en uno obligatorio no.
        for campo in CAMPOS_USUARIO_NO_NULOS:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo.")
        return self


class CambioContrasenaPropia(BaseModel):
    """Datos para que un usuario cambie su propia contraseña (requiere la actual)."""
    contrasena_actual: str = Field(min_length=1, max_length=128)
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
    # 'validation_alias' lee la propiedad Python 'permisos_lista' del modelo ORM (lista ya
    # convertida), no la columna cruda 'permisos' (texto con comas), que es un detalle interno.
    permisos: list[str] = Field(default_factory=list, validation_alias="permisos_lista")

    model_config = {"from_attributes": True, "populate_by_name": True}


class PermisoDisponible(BaseModel):
    """Un permiso del catálogo del sistema, para que el frontend arme la lista de checkboxes."""
    clave: str
    descripcion: str