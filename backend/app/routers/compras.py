# Ruta: backend/app/routers/compras.py
# Endpoint para registrar compras a proveedores. Al confirmar una compra, el
# inventario de cada producto involucrado aumenta automáticamente y se actualiza
# su precio de compra con el costo más reciente.
#
# PERMISOS: todo este módulo requiere el permiso granular "compras_gestionar"
# (el administrador siempre lo tiene por su rol; un empleado solo si el
# administrador se lo asignó desde Usuarios).
#
# CAMBIOS EN ESTA VERSIÓN:
# - No se aceptan productos inactivos (eliminados) dentro de una compra.
# - Cada compra queda registrada en logs/negocio.log (quién, a quién y cuánto).
# - El listado tiene un límite de filas para no devolver todo el historial.

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.logs.logger import registrar_negocio
from app.models.compra import Compra, DetalleCompra
from app.models.producto import Producto
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.schemas.compra import CompraCrear, CompraRespuesta, DetalleCompraRespuesta

router = APIRouter(prefix="/api/compras", tags=["Compras"])


def _construir_respuesta(compra: Compra) -> CompraRespuesta:
    """Convierte una compra y sus detalles en el esquema de respuesta para el frontend."""
    detalles_respuesta = [
        DetalleCompraRespuesta(
            id=detalle.id,
            producto_id=detalle.producto_id,
            nombre_producto=detalle.producto.nombre,
            cantidad=detalle.cantidad,
            costo_unitario=detalle.costo_unitario,
            subtotal=detalle.subtotal,
        )
        for detalle in compra.detalles
    ]
    return CompraRespuesta(
        id=compra.id,
        proveedor_id=compra.proveedor_id,
        nombre_proveedor=compra.proveedor.nombre,
        fecha=compra.fecha,
        total=compra.total,
        detalles=detalles_respuesta,
    )


@router.get("/", response_model=list[CompraRespuesta])
def listar_compras(
    limite: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Lista el historial de compras, de la más reciente a la más antigua (con límite de filas)."""
    compras = (
        db.query(Compra)
        .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto), joinedload(Compra.proveedor))
        .order_by(Compra.fecha.desc())
        .limit(limite)
        .all()
    )
    return [_construir_respuesta(c) for c in compras]


@router.get("/{compra_id}", response_model=CompraRespuesta)
def obtener_compra(
    compra_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Obtiene el detalle completo de una compra."""
    compra = (
        db.query(Compra)
        .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto), joinedload(Compra.proveedor))
        .filter(Compra.id == compra_id)
        .first()
    )
    if not compra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compra no encontrada")
    return _construir_respuesta(compra)


@router.post("/", response_model=CompraRespuesta, status_code=status.HTTP_201_CREATED)
def registrar_compra(
    request: Request,
    datos: CompraCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("compras_gestionar")),
):
    """
    Registra una compra completa a un proveedor (con uno o varios productos).
    Aumenta automáticamente el stock de cada producto y actualiza su precio de
    compra con el costo unitario más reciente. Deja constancia en negocio.log.
    """
    proveedor = db.query(Proveedor).filter(Proveedor.id == datos.proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    nueva_compra = Compra(proveedor_id=proveedor.id, usuario_id=usuario.id, total=0)
    db.add(nueva_compra)
    db.flush()  # Genera el id de la compra antes de crear sus detalles

    total_calculado = 0.0
    resumen_productos: list[str] = []
    for item in datos.items:
        # Solo se pueden comprar productos activos (los eliminados ya no están en el catálogo)
        producto = (
            db.query(Producto)
            .filter(Producto.id == item.producto_id, Producto.activo.is_(True))
            .first()
        )
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con id {item.producto_id} no encontrado o inactivo",
            )

        db.add(
            DetalleCompra(
                compra_id=nueva_compra.id,
                producto_id=producto.id,
                cantidad=item.cantidad,
                costo_unitario=item.costo_unitario,
            )
        )
        total_calculado += item.cantidad * item.costo_unitario
        resumen_productos.append(f"{item.cantidad}x {producto.nombre}")

        # Aumenta el inventario y actualiza el costo de compra vigente
        producto.stock_actual += item.cantidad
        producto.precio_compra = item.costo_unitario

    nueva_compra.total = round(total_calculado, 2)
    db.commit()
    db.refresh(nueva_compra)

    registrar_negocio(
        accion=f"Registró la compra #{nueva_compra.id} al proveedor '{proveedor.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Total: ${nueva_compra.total:,.0f} | Productos: {', '.join(resumen_productos)}",
        request=request,
    )
    return _construir_respuesta(nueva_compra)