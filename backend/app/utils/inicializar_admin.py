# Ruta: backend/app/utils/inicializar_admin.py
# Crea el primer usuario administrador automáticamente, únicamente si todavía no
# existe ningún usuario. CORRECCIÓN: si dos instancias arrancan a la vez (Vercel)
# y ambas intentan crearlo, la segunda captura el error de duplicado en vez de
# fallar el arranque.

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import configuracion
from app.models.usuario import Usuario, RolUsuario
from app.security import cifrar_contrasena


def crear_administrador_inicial(db: Session) -> None:
    """Inserta el usuario administrador definido en el entorno si la tabla de usuarios está vacía."""
    if db.query(Usuario.id).first():
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # Otra instancia lo creó primero: no hay nada más que hacer