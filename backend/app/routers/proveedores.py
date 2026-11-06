# Ruta: backend/app/routers/proveedores.py
# Endpoints para gestionar los proveedores del negocio.
#
# PERMISOS: todo este módulo requiere el permiso granular "compras_gestionar" (el
# administrador siempre lo tiene por su rol; un empleado solo si se lo asignaron). Es el
# mismo permiso que el de compras (routers/compras.py) porque en el frontend proveedores
# y compras se gestionan como un solo módulo.
#
# CAMBIOS: crear, editar y eliminar quedan en el log de negocio; el import de Compra sube
# al inicio del archivo; si se registra una compra justo al eliminar un proveedor, la
# llave foránea responde 400 en vez de un error 500.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.logs.logger import registrar_negocio
from app.models.compra import Compra
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.schemas.proveedor import ProveedorCrear, ProveedorActualizar, ProveedorRespuesta

router = APIRouter(prefix="/api/proveedores", tags=["Proveedores"])

MENSAJE_CON_COMPRAS = "No se puede eliminar: el proveedor tiene compras registradas"


@router.get("/", response_model=list[ProveedorRespuesta])
def listar_proveedores(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Lista todos los proveedores registrados."""
    return db.query(Proveedor).order_by(Proveedor.nombre).all()


@router.post("/", response_model=ProveedorRespuesta, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    request: Request,
    datos: ProveedorCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("compras_gestionar")),
):
    """Registra un nuevo proveedor."""
    nuevo_proveedor = Proveedor(**datos.model_dump())
    db.add(nuevo_proveedor)
    db.commit()
    db.refresh(nuevo_proveedor)

    registrar_negocio(
        accion=f"Creó el proveedor #{nuevo_proveedor.id} '{nuevo_proveedor.nombre}'",
        usuario=usuario.nombre_usuario,
        request=request,
    )
    return nuevo_proveedor


@router.put("/{proveedor_id}", response_model=ProveedorRespuesta)
def actualizar_proveedor(
    request: Request,
    proveedor_id: int,
    datos: ProveedorActualizar,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("compras_gestionar")),
):
    """Actualiza los datos de un proveedor existente."""
    proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(proveedor, campo, valor)

    db.commit()
    db.refresh(proveedor)

    registrar_negocio(
        accion=f"Modificó el proveedor #{proveedor.id} '{proveedor.nombre}'",
        usuario=usuario.nombre_usuario,
        request=request,
    )
    return proveedor


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proveedor(
    request: Request,
    proveedor_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("compras_gestionar")),
):
    """Elimina un proveedor (solo si no tiene compras registradas asociadas)."""
    proveedor = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    if db.query(Compra.id).filter(Compra.proveedor_id == proveedor_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MENSAJE_CON_COMPRAS)

    nombre = proveedor.nombre
    db.delete(proveedor)
    try:
        db.commit()
    except IntegrityError:
        # Una compra se registró a este proveedor en el mismo instante
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MENSAJE_CON_COMPRAS)

    registrar_negocio(
        accion=f"Eliminó el proveedor #{proveedor_id} '{nombre}'",
        usuario=usuario.nombre_usuario,
        request=request,
    )