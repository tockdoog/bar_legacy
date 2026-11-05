# Ruta: backend/app/routers/mesas.py
# Endpoints para gestionar las mesas del negocio: crear, listar (con su estado
# y venta abierta si la tiene), actualizar y eliminar.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.mesa import Mesa, EstadoMesa
from app.models.venta import Venta, EstadoVenta
from app.models.usuario import RolUsuario
from app.schemas.mesa import MesaCrear, MesaActualizar, MesaRespuesta

router = APIRouter(prefix="/api/mesas", tags=["Mesas"])


def _convertir_a_respuesta(mesa: Mesa, db: Session) -> MesaRespuesta:
    """Arma la respuesta de una mesa agregando el id de su venta abierta, si existe."""
    venta_abierta = (
        db.query(Venta)
        .filter(Venta.mesa_id == mesa.id, Venta.estado == EstadoVenta.ABIERTA)
        .first()
    )
    return MesaRespuesta(
        id=mesa.id,
        numero=mesa.numero,
        estado=mesa.estado,
        venta_abierta_id=venta_abierta.id if venta_abierta else None,
    )


@router.get("/", response_model=list[MesaRespuesta])
def listar_mesas(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista todas las mesas ordenadas por número, junto con su estado actual."""
    mesas = db.query(Mesa).order_by(Mesa.numero).all()
    return [_convertir_a_respuesta(mesa, db) for mesa in mesas]


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

    for campo, valor in datos.model_dump(exclude_unset=True).items():
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

    db.delete(mesa)
    db.commit()