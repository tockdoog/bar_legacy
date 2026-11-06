# Ruta: backend/app/routers/usuarios.py
# Endpoints para la gestión de usuarios: el administrador puede listar, crear, editar,
# activar/desactivar, restablecer contraseñas y asignar permisos granulares a los
# empleados; cualquier usuario autenticado puede cambiar su propia contraseña.
#
# CAMBIOS EN ESTA VERSIÓN:
# - Dos solicitudes simultáneas con el mismo usuario o correo responden 400 (antes 500).
# - Al quitar el rol o desactivar a un administrador se bloquean las filas de los demás
#   administradores activos: dos cambios simultáneos ya no pueden dejar el sistema sin ninguno.
# - Cambiar la propia contraseña queda limitado a 5 intentos por minuto.
# - Una contraseña de más de 72 bytes responde 400 en vez de 500.
# - Los cambios sensibles quedan en el log del sistema, sin guardar nunca la contraseña.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import obtener_usuario_actual, requerir_rol
from app.logs.logger import registrar_sistema
from app.models.usuario import Usuario, RolUsuario
from app.permisos import CATALOGO_PERMISOS
from app.schemas.usuario import (
    UsuarioCrear,
    UsuarioActualizar,
    UsuarioRespuesta,
    CambioContrasenaPropia,
    RestablecerContrasena,
    PermisoDisponible,
)
from app.security import cifrar_contrasena, verificar_contrasena
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


def _cifrar_o_400(contrasena: str) -> str:
    """Cifra la contraseña; si supera el límite de bcrypt (72 bytes) responde 400 en vez de 500."""
    try:
        return cifrar_contrasena(contrasena)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


def _confirmar_o_rechazar_duplicado(db: Session) -> None:
    """
    Confirma los cambios. Si otra petición creó o cambió al mismo tiempo el mismo
    usuario o correo, la restricción única de la base de datos falla: se responde 400.
    """
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario o el correo ya están registrados.",
        )


@router.get("/", response_model=list[UsuarioRespuesta])
def listar_usuarios(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Lista todos los usuarios registrados en el sistema."""
    return db.query(Usuario).order_by(Usuario.nombre_completo).all()


@router.get("/permisos-disponibles", response_model=list[PermisoDisponible])
def listar_permisos_disponibles(
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """
    Devuelve el catálogo de permisos granulares que el administrador puede asignar a un
    empleado, para que el frontend arme las casillas del formulario sin duplicar textos.
    """
    return [
        PermisoDisponible(clave=clave, descripcion=descripcion)
        for clave, descripcion in CATALOGO_PERMISOS.items()
    ]


@router.post("/", response_model=UsuarioRespuesta, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Crea un nuevo usuario (administrador o empleado, con permisos si aplica)."""
    if db.query(Usuario).filter(Usuario.nombre_usuario == datos.nombre_usuario).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ese nombre de usuario ya está en uso")
    if db.query(Usuario).filter(Usuario.correo == datos.correo).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ese correo ya está registrado")

    nuevo_usuario = Usuario(
        nombre_completo=datos.nombre_completo,
        nombre_usuario=datos.nombre_usuario,
        correo=datos.correo,
        contrasena_hash=_cifrar_o_400(datos.contrasena),
        rol=datos.rol,
        activo=True,
    )

    # Los permisos granulares solo aplican a empleados: un administrador ya tiene
    # acceso completo por su rol, así que se ignoran para esa cuenta.
    nuevo_usuario.establecer_permisos_lista(
        datos.permisos if datos.rol == RolUsuario.EMPLEADO else []
    )

    db.add(nuevo_usuario)
    _confirmar_o_rechazar_duplicado(db)
    db.refresh(nuevo_usuario)

    registrar_sistema(
        f"Creó el usuario '{nuevo_usuario.nombre_usuario}' con rol {nuevo_usuario.rol.value}",
        usuario=usuario.nombre_usuario,
    )
    return nuevo_usuario


@router.put("/{usuario_id}", response_model=UsuarioRespuesta)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(obtener_db),
    usuario_actual: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Actualiza los datos, el rol, el estado (activo/inactivo) o los permisos de un usuario."""
    usuario_objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    datos_dict = datos.model_dump(exclude_unset=True)
    # Los permisos se manejan aparte (pasan por establecer_permisos_lista())
    permisos_nuevos = datos_dict.pop("permisos", None)

    # Bloque: un administrador no puede quitarse a sí mismo el rol ni desactivarse
    if usuario_objetivo.id == usuario_actual.id:
        if datos_dict.get("activo") is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes desactivar tu propia cuenta")
        if datos_dict.get("rol") == RolUsuario.EMPLEADO:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes quitarte tu propio rol de administrador")

    # Bloque: no se puede dejar el sistema sin ningún administrador activo. Se bloquean
    # las filas de los demás administradores para que dos cambios simultáneos no
    # puedan saltarse esta regla.
    si_se_desactiva = datos_dict.get("activo") is False
    si_se_quita_admin = datos_dict.get("rol") == RolUsuario.EMPLEADO
    if (si_se_desactiva or si_se_quita_admin) and usuario_objetivo.rol == RolUsuario.ADMINISTRADOR:
        otros_admins_activos = (
            db.query(Usuario.id)
            .filter(
                Usuario.rol == RolUsuario.ADMINISTRADOR,
                Usuario.activo.is_(True),
                Usuario.id != usuario_objetivo.id,
            )
            .with_for_update()
            .all()
        )
        if not otros_admins_activos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe quedar al menos un administrador activo en el sistema",
            )

    if "correo" in datos_dict:
        correo_en_uso = (
            db.query(Usuario.id)
            .filter(Usuario.correo == datos_dict["correo"], Usuario.id != usuario_id)
            .first()
        )
        if correo_en_uso:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ese correo ya está en uso por otro usuario")

    rol_anterior = usuario_objetivo.rol
    activo_anterior = usuario_objetivo.activo

    for campo, valor in datos_dict.items():
        setattr(usuario_objetivo, campo, valor)

    # Un administrador no depende de permisos granulares: su lista se vacía
    if usuario_objetivo.rol == RolUsuario.ADMINISTRADOR:
        usuario_objetivo.establecer_permisos_lista([])
    elif permisos_nuevos is not None:
        usuario_objetivo.establecer_permisos_lista(permisos_nuevos)

    _confirmar_o_rechazar_duplicado(db)
    db.refresh(usuario_objetivo)

    # Bloque: deja constancia de los cambios sensibles (rol, estado y permisos)
    cambios = []
    if usuario_objetivo.rol != rol_anterior:
        cambios.append(f"rol {rol_anterior.value} -> {usuario_objetivo.rol.value}")
    if usuario_objetivo.activo != activo_anterior:
        cambios.append("activó la cuenta" if usuario_objetivo.activo else "desactivó la cuenta")
    if permisos_nuevos is not None:
        cambios.append(f"permisos: {','.join(usuario_objetivo.permisos_lista) or 'ninguno'}")
    registrar_sistema(
        f"Editó al usuario '{usuario_objetivo.nombre_usuario}'" + (f" ({'; '.join(cambios)})" if cambios else ""),
        usuario=usuario_actual.nombre_usuario,
    )
    return usuario_objetivo


@router.post("/{usuario_id}/restablecer-contrasena", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_contrasena(
    usuario_id: int,
    datos: RestablecerContrasena,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Permite al administrador asignar una nueva contraseña a otro usuario (ej: la olvidó)."""
    usuario_objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    usuario_objetivo.contrasena_hash = _cifrar_o_400(datos.contrasena_nueva)
    usuario_objetivo.intentos_fallidos = 0
    usuario_objetivo.bloqueado_hasta = None
    db.commit()

    registrar_sistema(
        f"Restableció la contraseña del usuario '{usuario_objetivo.nombre_usuario}'",
        usuario=usuario.nombre_usuario,
    )


@router.put("/me/contrasena", status_code=status.HTTP_204_NO_CONTENT)
@limitador.limit("5/minute")  # Frena adivinar la contraseña actual con un token robado
def cambiar_mi_contrasena(
    request: Request,
    datos: CambioContrasenaPropia,
    db: Session = Depends(obtener_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Permite a cualquier usuario autenticado cambiar su propia contraseña."""
    if not verificar_contrasena(datos.contrasena_actual, usuario_actual.contrasena_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")

    usuario_actual.contrasena_hash = _cifrar_o_400(datos.contrasena_nueva)
    db.commit()

    registrar_sistema("Cambió su propia contraseña", usuario=usuario_actual.nombre_usuario)