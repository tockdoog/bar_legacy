# Ruta: backend/app/routers/proveedores.py
# Endpoints para gestionar los proveedores del negocio.
#
# PERMISOS: todo este módulo requiere el permiso granular "compras_gestionar"
# (el administrador siempre lo tiene por su rol; un empleado solo si el
# administrador se lo asignó desde Usuarios). Se usa el mismo permiso que el
# router de compras (app/routers/compras.py) porque en el frontend
# (compras.js) proveedores y compras se gestionan como un solo módulo de
# negocio: quien puede registrar una compra necesita poder ver y mantener
# también el catálogo de proveedores a los que le compra.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.models.proveedor import Proveedor
from app.schemas.proveedor import ProveedorCrear, ProveedorActualizar, ProveedorRespuesta

router = APIRouter(prefix="/api/proveedores", tags=["Proveedores"])


@router.get("/", response_model=list[ProveedorRespuesta])
def listar_proveedores(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Lista todos los proveedores registrados."""
    return db.query(Proveedor).order_by(Proveedor.nombre).all()


@router.post("/", response_model=ProveedorRespuesta, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    datos: ProveedorCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Registra un nuevo proveedor."""
    nuevo_proveedor = Proveedor(**datos.model_dump())
    db.add(nuevo_proveedor)
    db.commit()
    db.refresh(nuevo_proveedor)
    return nuevo_proveedor


@router.put("/{proveedor_id}", response_model=ProveedorRespuesta)
def actualizar_proveedor(
    proveedor_id: int,
    datos: ProveedorActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Actualiza los datos de un proveedor existente."""
    proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(proveedor, campo, valor)

    db.commit()
    db.refresh(proveedor)
    return proveedor


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Elimina un proveedor (solo si no tiene compras registradas asociadas)."""
    from app.models.compra import Compra

    proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    tiene_compras = db.query(Compra).filter(Compra.proveedor_id == proveedor_id).first()
    if tiene_compras:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar: el proveedor tiene compras registradas",
        )

    db.delete(proveedor)
    db.commit()