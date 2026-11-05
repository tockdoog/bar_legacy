# Ruta: backend/app/utils/inicializar_admin.py
# Crea el primer usuario administrador automáticamente al iniciar el servidor,
# únicamente si todavía no existe ningún usuario registrado en la base de datos.

from sqlalchemy.orm import Session

from app.config import configuracion
from app.models.usuario import Usuario, RolUsuario
from app.security import cifrar_contrasena


def crear_administrador_inicial(db: Session) -> None:
    """Inserta el usuario administrador definido en el .env si la tabla de usuarios está vacía."""
    existe_algun_usuario = db.query(Usuario).first()
    if existe_algun_usuario:
        return  # Ya hay usuarios creados, no se hace nada

    admin = Usuario(
        nombre_completo=configuracion.ADMIN_NOMBRE,
        nombre_usuario=configuracion.ADMIN_USUARIO,
        correo=configuracion.ADMIN_CORREO,
        contrasena_hash=cifrar_contrasena(configuracion.ADMIN_CONTRASENA),
        rol=RolUsuario.ADMINISTRADOR,
        activo=True,
    )
    db.add(admin)
    db.commit()