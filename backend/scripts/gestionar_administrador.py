# Ruta: backend/scripts/gestionar_administrador.py
# Permite crear un nuevo usuario administrador o restablecer la contraseña de
# uno existente, sin depender de que la base de datos esté vacía (a diferencia
# de la creación automática en app/utils/inicializar_admin.py).

import getpass

from _configuracion_scripts import obtener_sesion, confirmar_accion
from app.models.usuario import Usuario, RolUsuario
from app.security import cifrar_contrasena


def pedir_contrasena_segura() -> str:
    """Solicita una contraseña por consola sin mostrarla en pantalla, con validación mínima."""
    while True:
        contrasena = getpass.getpass("Nueva contraseña (mínimo 8 caracteres): ")
        if len(contrasena) < 8:
            print("La contraseña es demasiado corta, intenta de nuevo.")
            continue
        confirmacion = getpass.getpass("Confirma la contraseña: ")
        if contrasena != confirmacion:
            print("Las contraseñas no coinciden, intenta de nuevo.")
            continue
        return contrasena


def listar_administradores() -> None:
    """Muestra todos los usuarios con rol administrador."""
    db = obtener_sesion()
    try:
        admins = db.query(Usuario).filter(Usuario.rol == RolUsuario.ADMINISTRADOR).all()
        if not admins:
            print("No hay administradores registrados.")
            return
        print("\nAdministradores registrados:")
        for admin in admins:
            estado = "activo" if admin.activo else "inactivo"
            print(f"  - {admin.nombre_usuario} ({admin.correo}) [{estado}]")
    finally:
        db.close()


def crear_o_actualizar_administrador() -> None:
    """Crea un nuevo administrador o, si el nombre de usuario ya existe, restablece su contraseña."""
    nombre_usuario = input("Nombre de usuario: ").strip()
    if not nombre_usuario:
        print("El nombre de usuario no puede estar vacío.")
        return

    db = obtener_sesion()
    try:
        usuario = db.query(Usuario).filter(Usuario.nombre_usuario == nombre_usuario).first()
        nueva_contrasena = pedir_contrasena_segura()

        if usuario:
            if not confirmar_accion(f"El usuario '{nombre_usuario}' ya existe. ¿Restablecer su contraseña?"):
                print("Operación cancelada.")
                return
            usuario.contrasena_hash = cifrar_contrasena(nueva_contrasena)
            usuario.rol = RolUsuario.ADMINISTRADOR
            usuario.activo = True
            db.commit()
            print(f"Contraseña de '{nombre_usuario}' restablecida y rol asegurado como administrador.")
        else:
            correo = input("Correo electrónico: ").strip()
            nombre_completo = input("Nombre completo: ").strip() or nombre_usuario

            nuevo_admin = Usuario(
                nombre_completo=nombre_completo,
                nombre_usuario=nombre_usuario,
                correo=correo,
                contrasena_hash=cifrar_contrasena(nueva_contrasena),
                rol=RolUsuario.ADMINISTRADOR,
                activo=True,
            )
            db.add(nuevo_admin)
            db.commit()
            print(f"Administrador '{nombre_usuario}' creado correctamente.")
    finally:
        db.close()


def main() -> None:
    print("=" * 60)
    print("GESTIONAR USUARIO ADMINISTRADOR")
    print("=" * 60)
    print("1. Crear administrador / restablecer contraseña")
    print("2. Listar administradores")
    opcion = input("Elige una opción: ").strip()

    if opcion == "1":
        crear_o_actualizar_administrador()
    elif opcion == "2":
        listar_administradores()
    else:
        print("Opción no válida.")


if __name__ == "__main__":
    main()