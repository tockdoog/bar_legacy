# Ruta: backend/app/dependencies.py
# Dependencias reutilizables de FastAPI: obtener el usuario autenticado desde
# el token JWT, validar que tenga el rol requerido, y validar que tenga un
# permiso granular puntual (para empleados con acceso ampliado). También
# registra en el módulo de monitoreo los intentos sospechosos.
# Sistema de uso general, sin relación con ningún nicho de negocio específico.

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models.usuario import Usuario, RolUsuario
from app.security import decodificar_token
from app.logs.logger import registrar_seguridad

# Indica a FastAPI dónde se obtiene el token (usado también para la
# documentación /docs). Se usa ruta absoluta ("/api/...") para que el botón
# "Authorize" de Swagger construya bien la URL sin importar si /docs se ve
# a través del proxy inverso de Nginx o directo contra el backend.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def obtener_usuario_actual(
    request: Request,
    token: str = Depends(esquema_oauth2),
    db: Session = Depends(obtener_db),
) -> Usuario:
    """
    Decodifica el token JWT recibido en cada petición y devuelve el usuario
    correspondiente. Si el token es inválido, expiró o el usuario fue
    desactivado, se rechaza la petición con un error 401 y se registra el
    intento en el log de seguridad.

    IMPORTANTE: el rol y los permisos del usuario SIEMPRE se leen de la base
    de datos (nunca del contenido del token). Esto evita que un usuario cuyo
    rol o permisos fueron modificados (ej. de administrador a empleado, o se
    le quitó un permiso) conserve el acceso anterior mientras su token
    previo siga vigente: en la próxima petición, este mismo bloque ya trae
    los datos actualizados desde la base de datos.
    """
    error_credenciales = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No fue posible validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    datos = decodificar_token(token)
    if datos is None or "id_usuario" not in datos:
        registrar_seguridad("Token inválido o expirado presentado", request=request)
        raise error_credenciales

    # Valida que "id_usuario" tenga un formato numérico válido antes de usarlo
    # en la consulta. Un token manipulado a mano (o de otro sistema firmado
    # con una clave filtrada) podría traer un valor no numérico en este
    # campo; sin esta validación, la consulta lanzaría una excepción no
    # controlada (error 500) en vez de un 401 limpio.
    try:
        id_usuario = int(datos["id_usuario"])
    except (TypeError, ValueError):
        registrar_seguridad("Token con id_usuario en formato inválido", request=request)
        raise error_credenciales

    usuario = db.query(Usuario).filter(Usuario.id == id_usuario).first()
    if usuario is None or not usuario.activo:
        registrar_seguridad(
            "Token válido pero el usuario no existe o está inactivo",
            request=request,
            usuario=str(id_usuario),
        )
        raise error_credenciales

    return usuario


def requerir_rol(*roles_permitidos: RolUsuario):
    """
    Fábrica de dependencias para restringir endpoints según el rol del usuario.
    Uso: Depends(requerir_rol(RolUsuario.ADMINISTRADOR))
    """

    def verificador(
        request: Request,
        usuario: Usuario = Depends(obtener_usuario_actual),
    ) -> Usuario:
        # Si el usuario autenticado no tiene el rol requerido, se rechaza el
        # acceso y se deja constancia en seguridad.log para su revisión
        if usuario.rol not in roles_permitidos:
            registrar_seguridad(
                f"Intento de acceso sin permisos suficientes a {request.url.path}",
                request=request,
                usuario=usuario.nombre_usuario,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción",
            )
        return usuario

    return verificador


def requerir_permiso(clave_permiso: str):
    """
    Fábrica de dependencias para restringir un endpoint a un permiso
    granular puntual (ver app/permisos.py para el catálogo completo).

    Reglas:
    - El administrador SIEMPRE pasa, sin importar el permiso pedido: su rol
      ya implica acceso completo al sistema.
    - Un empleado solo pasa si 'clave_permiso' está dentro de la lista de
      permisos que el administrador le asignó (usuario.permisos_lista).

    Uso: Depends(requerir_permiso("inventario_gestionar"))
    """

    def verificador(
        request: Request,
        usuario: Usuario = Depends(obtener_usuario_actual),
    ) -> Usuario:
        if usuario.rol == RolUsuario.ADMINISTRADOR:
            return usuario

        if clave_permiso in usuario.permisos_lista:
            return usuario

        registrar_seguridad(
            f"Intento de acceso sin el permiso '{clave_permiso}' a {request.url.path}",
            request=request,
            usuario=usuario.nombre_usuario,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta acción",
        )

    return verificador