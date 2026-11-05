# Ruta: backend/app/schemas/auth.py
# Esquemas de datos para el proceso de inicio de sesión y el token de acceso.

from pydantic import BaseModel, Field


class TokenRespuesta(BaseModel):
    """Estructura de la respuesta que recibe el frontend al iniciar sesión correctamente."""
    token_acceso: str
    tipo_token: str = "bearer"
    rol: str
    nombre_completo: str
    # Lista de claves de permisos granulares del usuario (solo relevante
    # para empleados; para un administrador siempre llega vacía porque su
    # rol ya implica acceso completo, ver dependencies.requerir_permiso()).
    permisos: list[str] = Field(default_factory=list)


class DatosToken(BaseModel):
    """Información mínima que viaja codificada dentro del token JWT."""
    id_usuario: int | None = None
    rol: str | None = None