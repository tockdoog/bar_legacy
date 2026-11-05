# Ruta: backend/app/models/usuario.py
# Modelo de base de datos para los usuarios que ingresan al sistema
# (autenticación, roles y permisos granulares para empleados).

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text

from app.database import Base


class RolUsuario(str, enum.Enum):
    """Roles disponibles dentro del sistema, usados para controlar permisos."""
    ADMINISTRADOR = "administrador"
    EMPLEADO = "empleado"


class Usuario(Base):
    """Tabla que almacena las cuentas de acceso al sistema."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(120), nullable=False)
    nombre_usuario = Column(String(50), unique=True, index=True, nullable=False)
    correo = Column(String(120), unique=True, index=True, nullable=False)

    # Nunca se guarda la contraseña en texto plano, solo su hash (ver app/security.py)
    contrasena_hash = Column(String(255), nullable=False)

    rol = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.EMPLEADO)
    activo = Column(Boolean, default=True, nullable=False)

    # Permisos granulares, solo aplicables cuando rol == EMPLEADO. Se guardan
    # como texto con las claves separadas por coma (ej: "inventario_gestionar,
    # compras_gestionar") en vez de una tabla aparte, porque la cantidad de
    # permisos por usuario es pequeña y así se evita una migración más compleja
    # (tabla intermedia + relaciones) para un caso de uso simple. Un
    # administrador siempre tiene esta columna vacía: su rol ya le da acceso
    # completo, ver dependencies.requerir_permiso().
    permisos = Column(Text, nullable=True, default=None)

    # Control de intentos fallidos para mitigar ataques de fuerza bruta
    intentos_fallidos = Column(Integer, default=0, nullable=False)
    bloqueado_hasta = Column(DateTime, nullable=True)

    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def permisos_lista(self) -> list[str]:
        """Convierte el texto separado por comas guardado en 'permisos' a una lista de claves."""
        if not self.permisos:
            return []
        return [clave for clave in self.permisos.split(",") if clave]

    def establecer_permisos_lista(self, permisos: list[str]) -> None:
        """Reemplaza los permisos actuales del usuario a partir de una lista de claves."""
        claves_unicas = sorted(set(permisos)) if permisos else []
        self.permisos = ",".join(claves_unicas) if claves_unicas else None