# Ruta: backend/app/routers/usuarios.py
# Endpoints para la gestión de usuarios del sistema: el administrador puede
# listar, crear, editar, activar/desactivar, restablecer contraseñas y
# asignar permisos granulares a los empleados; cualquier usuario autenticado
# puede cambiar su propia contraseña.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import obtener_usuario_actual, requerir_rol
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

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


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
    Devuelve el catálogo de permisos granulares que el administrador puede
    asignar a un empleado, para que el frontend arme la lista de casillas
    del formulario de usuario sin duplicar esos textos.
    """
    return [
        PermisoDisponible(clave=clave, descripcion=descripcion)
        for clave, descripcion in CATALOGO_PERMISOS.items()
    ]


@router.post("/", response_model=UsuarioRespuesta, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
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
        contrasena_hash=cifrar_contrasena(datos.contrasena),
        rol=datos.rol,
        activo=True,
    )

    # Los permisos granulares solo aplican a empleados: un administrador ya
    # tiene acceso completo por su rol, así que cualquier permiso enviado
    # para una cuenta de administrador se ignora explícitamente.
    nuevo_usuario.establecer_permisos_lista(
        datos.permisos if datos.rol == RolUsuario.EMPLEADO else []
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
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
    # Los permisos se manejan aparte (no son un atributo directo del modelo,
    # sino que pasan por establecer_permisos_lista()), así que se sacan del
    # diccionario antes del bucle genérico de abajo.
    permisos_nuevos = datos_dict.pop("permisos", None)

    # No se permite que un administrador se quite a sí mismo el rol o se desactive,
    # para evitar quedar bloqueado fuera del sistema por accidente
    if usuario_objetivo.id == usuario_actual.id:
        if datos_dict.get("activo") is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes desactivar tu propia cuenta")
        if datos_dict.get("rol") == RolUsuario.EMPLEADO:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes quitarte tu propio rol de administrador")

    # No se permite dejar el sistema sin ningún administrador activo
    si_se_desactiva = datos_dict.get("activo") is False
    si_se_quita_admin = datos_dict.get("rol") == RolUsuario.EMPLEADO
    if (si_se_desactiva or si_se_quita_admin) and usuario_objetivo.rol == RolUsuario.ADMINISTRADOR:
        otros_admins_activos = (
            db.query(Usuario)
            .filter(Usuario.rol == RolUsuario.ADMINISTRADOR, Usuario.activo.is_(True), Usuario.id != usuario_objetivo.id)
            .first()
        )
        if not otros_admins_activos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe quedar al menos un administrador activo en el sistema",
            )

    if "correo" in datos_dict:
        correo_en_uso = (
            db.query(Usuario)
            .filter(Usuario.correo == datos_dict["correo"], Usuario.id != usuario_id)
            .first()
        )
        if correo_en_uso:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ese correo ya está en uso por otro usuario")

    for campo, valor in datos_dict.items():
        setattr(usuario_objetivo, campo, valor)

    # Si el usuario resultante es administrador (ya sea porque lo era o
    # porque se le acaba de asignar ese rol en esta misma petición), sus
    # permisos granulares se vacían: el rol de administrador ya otorga
    # acceso completo por sí mismo y no debe depender de esta lista.
    if usuario_objetivo.rol == RolUsuario.ADMINISTRADOR:
        usuario_objetivo.establecer_permisos_lista([])
    elif permisos_nuevos is not None:
        usuario_objetivo.establecer_permisos_lista(permisos_nuevos)

    db.commit()
    db.refresh(usuario_objetivo)
    return usuario_objetivo


@router.post("/{usuario_id}/restablecer-contrasena", status_code=status.HTTP_204_NO_CONTENT)
def restablecer_contrasena(
    usuario_id: int,
    datos: RestablecerContrasena,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Permite al administrador asignar una nueva contraseña a otro usuario (ej: la olvidó)."""
    usuario_objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    usuario_objetivo.contrasena_hash = cifrar_contrasena(datos.contrasena_nueva)
    usuario_objetivo.intentos_fallidos = 0
    usuario_objetivo.bloqueado_hasta = None
    db.commit()


@router.put("/me/contrasena", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_mi_contrasena(
    datos: CambioContrasenaPropia,
    db: Session = Depends(obtener_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Permite a cualquier usuario autenticado cambiar su propia contraseña."""
    if not verificar_contrasena(datos.contrasena_actual, usuario_actual.contrasena_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")

    usuario_actual.contrasena_hash = cifrar_contrasena(datos.contrasena_nueva)
    db.commit()