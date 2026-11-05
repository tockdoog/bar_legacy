# Ruta: backend/scripts/listar_usuarios.py
# Lista rápida de todos los usuarios del sistema con su rol, estado y si
# están bloqueados por intentos fallidos de inicio de sesión. Útil para
# verificar accesos sin necesidad de entrar por la interfaz web.

from datetime import datetime, timezone

from _configuracion_scripts import obtener_sesion
from app.models.usuario import Usuario


def main() -> None:
    print("=" * 60)
    print("LISTADO DE USUARIOS DEL SISTEMA")
    print("=" * 60)

    db = obtener_sesion()
    try:
        usuarios = db.query(Usuario).order_by(Usuario.id).all()
        if not usuarios:
            print("No hay usuarios registrados todavía.")
            return

        ahora = datetime.now(timezone.utc)
        for usuario in usuarios:
            estado = "activo" if usuario.activo else "INACTIVO"

            bloqueado = ""
            if usuario.bloqueado_hasta and usuario.bloqueado_hasta.replace(tzinfo=timezone.utc) > ahora:
                bloqueado = f" | BLOQUEADO hasta {usuario.bloqueado_hasta}"

            print(
                f"[{usuario.id}] {usuario.nombre_usuario} | {usuario.correo} | "
                f"rol: {usuario.rol.value} | estado: {estado} | "
                f"intentos fallidos: {usuario.intentos_fallidos}{bloqueado}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()