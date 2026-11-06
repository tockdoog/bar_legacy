# Ruta: backend/app/routers/compras.py
# Endpoint para registrar compras a proveedores. Al confirmar una compra, el inventario de
# cada producto involucrado aumenta automáticamente y se actualiza su precio de compra con
# el costo más reciente. Montos en pesos colombianos (COP).
#
# PERMISOS: todo este módulo requiere el permiso granular "compras_gestionar" (el
# administrador siempre lo tiene por su rol; un empleado solo si se lo asignaron).
#
# CAMBIOS EN ESTA VERSIÓN:
# - Los productos se bloquean en la base de datos (SELECT ... FOR UPDATE, en orden de id)
#   antes de sumar el stock: dos compras simultáneas del mismo producto ya no pierden una suma.
# - Si un mismo producto aparece dos veces en la compra, ambas líneas suman correctamente.
# - Todo se valida ANTES de crear la compra (antes se creaba y luego fallaba a mitad de camino).
# - Topes defensivos de cantidad y costo (evitan desbordar la columna entera de PostgreSQL).
# - Los montos del log de negocio usan formato colombiano ("$ 1.500").

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
from app.utils.formato_reportes import formatear_cop

router = APIRouter(prefix="/api/compras", tags=["Compras"])

# Topes defensivos (el esquema también debe validarlos)
CANTIDAD_MAXIMA_POR_LINEA = 1_000_000
COSTO_MAXIMO_UNITARIO = 1_000_000_000
STOCK_MAXIMO = 2_000_000_000  # Límite de la columna entera de PostgreSQL (2.147 millones)


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


def _consulta_compras(db: Session):
    """Consulta base que trae cada compra con sus detalles, productos y proveedor en una sola consulta."""
    return db.query(Compra).options(
        joinedload(Compra.detalles).joinedload(DetalleCompra.producto),
        joinedload(Compra.proveedor),
    )


@router.get("/", response_model=list[CompraRespuesta])
def listar_compras(
    limite: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Lista el historial de compras, de la más reciente a la más antigua (con límite de filas)."""
    compras = _consulta_compras(db).order_by(Compra.fecha.desc()).limit(limite).all()
    return [_construir_respuesta(c) for c in compras]


@router.get("/{compra_id}", response_model=CompraRespuesta)
def obtener_compra(
    compra_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("compras_gestionar")),
):
    """Obtiene el detalle completo de una compra."""
    compra = _consulta_compras(db).filter(Compra.id == compra_id).first()
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
    Registra una compra completa a un proveedor (con uno o varios productos). Aumenta el
    stock de cada producto y actualiza su precio de compra con el costo unitario más
    reciente. Deja constancia en el log de negocio.
    """
    proveedor = db.query(Proveedor).filter(Proveedor.id == datos.proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")

    # Bloque: bloquea los productos (en orden de id, para evitar bloqueos cruzados) y valida todo
    ids = sorted({item.producto_id for item in datos.items})
    productos = {
        producto.id: producto
        for producto in db.query(Producto)
        .filter(Producto.id.in_(ids), Producto.activo.is_(True))
        .order_by(Producto.id)
        .with_for_update()
        .all()
    }

    cantidades_por_producto: dict[int, int] = {}
    for item in datos.items:
        if item.producto_id not in productos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con id {item.producto_id} no encontrado o inactivo",
            )
        if item.cantidad > CANTIDAD_MAXIMA_POR_LINEA or item.costo_unitario > COSTO_MAXIMO_UNITARIO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad o el costo de un producto superan el máximo permitido.",
            )
        cantidades_por_producto[item.producto_id] = cantidades_por_producto.get(item.producto_id, 0) + item.cantidad

    for producto_id, cantidad in cantidades_por_producto.items():
        if productos[producto_id].stock_actual + cantidad > STOCK_MAXIMO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El stock de '{productos[producto_id].nombre}' superaría el máximo permitido.",
            )

    # Bloque: crea la compra y sus detalles, y actualiza el inventario
    nueva_compra = Compra(proveedor_id=proveedor.id, usuario_id=usuario.id, total=0)
    db.add(nueva_compra)
    db.flush()  # Genera el id de la compra antes de crear sus detalles

    total_calculado = 0.0
    resumen_productos: list[str] = []
    for item in datos.items:
        producto = productos[item.producto_id]
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

    compra = _consulta_compras(db).filter(Compra.id == nueva_compra.id).one()
    registrar_negocio(
        accion=f"Registró la compra #{compra.id} al proveedor '{proveedor.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Total: {formatear_cop(compra.total)} | Productos: {', '.join(resumen_productos)}",
        request=request,
    )
    return _construir_respuesta(compra)