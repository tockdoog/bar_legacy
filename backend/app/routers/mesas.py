# Ruta: backend/app/routers/mesas.py
# Endpoints para gestionar las mesas del negocio: crear, listar (con su estado y
# venta abierta si la tiene), actualizar y eliminar, más el bloqueo colaborativo
# por REST (reemplaza al WebSocket, que Vercel no soporta):
#   GET    /api/mesas/bloqueos            -> bloqueos vigentes
#   POST   /api/mesas/{id}/bloqueo        -> tomar o renovar (latido) el bloqueo
#   DELETE /api/mesas/{id}/bloqueo        -> liberar (solo el propio)
# Un bloqueo sin latido por TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS se considera libre.
# CAMBIO: listar_mesas hace una sola consulta de ventas abiertas (antes una por mesa).

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import configuracion
from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.bloqueo_mesa import BloqueoMesa
from app.models.mesa import Mesa, EstadoMesa
from app.models.usuario import RolUsuario, Usuario
from app.models.venta import Venta, EstadoVenta
from app.schemas.mesa import BloqueoMesaRespuesta, MesaActualizar, MesaCrear, MesaRespuesta
from app.utils.zona_horaria import ahora_colombia

router = APIRouter(prefix="/api/mesas", tags=["Mesas"])

_ROLES_POS = (RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)


def _convertir_a_respuesta(mesa: Mesa, db: Session) -> MesaRespuesta:
    """Arma la respuesta de una mesa agregando el id de su venta abierta, si existe."""
    venta_abierta = (
        db.query(Venta.id)
        .filter(Venta.mesa_id == mesa.id, Venta.estado == EstadoVenta.ABIERTA)
        .first()
    )
    return MesaRespuesta(
        id=mesa.id,
        numero=mesa.numero,
        estado=mesa.estado,
        venta_abierta_id=venta_abierta[0] if venta_abierta else None,
    )


def _a_bloqueo(bloqueo: BloqueoMesa, usuario: Usuario) -> BloqueoMesaRespuesta:
    """Convierte un bloqueo en su respuesta, indicando si pertenece a quien consulta."""
    return BloqueoMesaRespuesta(
        mesa_id=bloqueo.mesa_id,
        usuario_id=bloqueo.usuario_id,
        nombre_completo=bloqueo.nombre_completo,
        nombre_usuario=bloqueo.nombre_usuario,
        desde=bloqueo.desde,
        es_mio=bloqueo.usuario_id == usuario.id,
    )


def _limite_expiracion():
    """Fecha anterior a la cual un latido ya se considera vencido."""
    return ahora_colombia() - timedelta(seconds=configuracion.TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS)


@router.get("/", response_model=list[MesaRespuesta])
def listar_mesas(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Lista todas las mesas ordenadas por número, junto con su estado actual."""
    mesas = db.query(Mesa).order_by(Mesa.numero).all()
    # Una sola consulta con todas las ventas abiertas de mesa
    abiertas = dict(
        db.query(Venta.mesa_id, Venta.id)
        .filter(Venta.mesa_id.isnot(None), Venta.estado == EstadoVenta.ABIERTA)
        .all()
    )
    return [
        MesaRespuesta(id=m.id, numero=m.numero, estado=m.estado, venta_abierta_id=abiertas.get(m.id))
        for m in mesas
    ]


@router.get("/bloqueos", response_model=list[BloqueoMesaRespuesta])
def listar_bloqueos(
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """Lista los bloqueos vigentes (con latido reciente) para pintar quién atiende cada mesa."""
    vigentes = db.query(BloqueoMesa).filter(BloqueoMesa.ultimo_latido >= _limite_expiracion()).all()
    return [_a_bloqueo(b, usuario) for b in vigentes]


@router.post("/{mesa_id}/bloqueo", response_model=BloqueoMesaRespuesta)
def tomar_bloqueo(
    mesa_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Toma el bloqueo de una mesa o lo renueva (latido) si ya es del usuario. Si lo
    tiene otro usuario con latido vigente responde 409; si ese latido venció, el
    bloqueo se transfiere a quien lo pide.
    """
    mesa = db.query(Mesa).filter(Mesa.id == mesa_id).first()
    if not mesa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa no encontrada")

    ahora = ahora_colombia()
    # with_for_update evita que dos usuarios tomen la mesa al mismo tiempo (PostgreSQL)
    bloqueo = db.query(BloqueoMesa).filter(BloqueoMesa.mesa_id == mesa_id).with_for_update().first()

    if bloqueo and bloqueo.usuario_id != usuario.id and bloqueo.ultimo_latido >= _limite_expiracion():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La mesa {mesa.numero} la está atendiendo {bloqueo.nombre_completo}.",
        )

    if bloqueo is None:
        bloqueo = BloqueoMesa(mesa_id=mesa_id, desde=ahora)
        db.add(bloqueo)
    if bloqueo.usuario_id != usuario.id:
        # Mesa nueva o con bloqueo vencido de otro usuario: pasa a este usuario
        bloqueo.usuario_id = usuario.id
        bloqueo.nombre_completo = usuario.nombre_completo
        bloqueo.nombre_usuario = usuario.nombre_usuario
        bloqueo.desde = ahora
    bloqueo.ultimo_latido = ahora

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Otro usuario tomó la mesa {mesa.numero} en este instante. Intenta de nuevo.",
        )
    db.refresh(bloqueo)
    return _a_bloqueo(bloqueo, usuario)


@router.delete("/{mesa_id}/bloqueo", status_code=status.HTTP_204_NO_CONTENT)
def liberar_bloqueo(
    mesa_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """Libera el bloqueo de una mesa, solo si lo tiene quien lo pide (si no, no hace nada)."""
    db.query(BloqueoMesa).filter(
        BloqueoMesa.mesa_id == mesa_id, BloqueoMesa.usuario_id == usuario.id
    ).delete()
    db.commit()


@router.post("/", response_model=MesaRespuesta, status_code=status.HTTP_201_CREATED)
def crear_mesa(
    datos: MesaCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Registra una nueva mesa, siempre con estado inicial 'libre'."""
    if db.query(Mesa).filter(Mesa.numero == datos.numero).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe una mesa con ese número")

    nueva_mesa = Mesa(numero=datos.numero, estado=EstadoMesa.LIBRE)
    db.add(nueva_mesa)
    db.commit()
    db.refresh(nueva_mesa)
    return _convertir_a_respuesta(nueva_mesa, db)


@router.put("/{mesa_id}", response_model=MesaRespuesta)
def actualizar_mesa(
    mesa_id: int,
    datos: MesaActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Actualiza el número o el estado de una mesa de forma manual."""
    mesa = db.query(Mesa).filter(Mesa.id == mesa_id).first()
    if not mesa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa no encontrada")

    cambios = datos.model_dump(exclude_unset=True)
    # Número y estado son obligatorios en la base de datos: no pueden quedar nulos
    for campo, valor in cambios.items():
        if valor is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El campo '{campo}' no puede quedar vacío")
        setattr(mesa, campo, valor)

    db.commit()
    db.refresh(mesa)
    return _convertir_a_respuesta(mesa, db)


@router.delete("/{mesa_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mesa(
    mesa_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Elimina una mesa, siempre que no tenga una venta abierta en curso."""
    mesa = db.query(Mesa).filter(Mesa.id == mesa_id).first()
    if not mesa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa no encontrada")

    if mesa.estado != EstadoMesa.LIBRE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede eliminar una mesa que está en uso")

    # El bloqueo se borra primero (en PostgreSQL la llave foránea lo exigiría)
    db.query(BloqueoMesa).filter(BloqueoMesa.mesa_id == mesa_id).delete()
    db.delete(mesa)
    db.commit()