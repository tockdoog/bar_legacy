# Ruta: backend/app/routers/promociones.py
# Endpoints para crear, listar, actualizar y desactivar promociones (combos de productos
# vendidos a un precio especial, ej: "2 cervezas + snack"). Precios en pesos colombianos (COP).
#
# SEGURIDAD (datos financieros sensibles): el costo de un producto (precio_compra) nunca
# debe llegar a un EMPLEADO, porque revela el margen de utilidad. _construir_respuesta()
# solo calcula costo, ganancia y margen cuando quien consulta es ADMINISTRADOR.
#
# CAMBIOS EN ESTA VERSIÓN:
# - Los montos del log de negocio usan formato colombiano ("$ 1.500", antes "$1,500").
# - Los productos de una promoción se validan con UNA consulta (antes una por producto,
#   lento con Neon) y las respuestas cargan los componentes en una sola consulta.
# - Los nulos en campos obligatorios y los topes ahora los valida el esquema (422).
# - GET admite ?incluir_inactivas=true (solo para el administrador) para poder reactivar.

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.logs.logger import registrar_negocio
from app.models.producto import Producto
from app.models.promocion import Promocion, ComponentePromocion
from app.models.usuario import RolUsuario, Usuario
from app.schemas.promocion import (
    PromocionCrear,
    PromocionActualizar,
    PromocionRespuesta,
    ComponentePromocionRespuesta,
    ComponentePromocionCrear,
)
from app.utils.formato_reportes import formatear_cop

router = APIRouter(prefix="/api/promociones", tags=["Promociones"])


def _consulta_promociones(db: Session):
    """Consulta base que trae cada promoción con sus componentes y productos en una sola consulta."""
    return db.query(Promocion).options(
        joinedload(Promocion.componentes).joinedload(ComponentePromocion.producto)
    )


def _construir_respuesta(promocion: Promocion, usuario: Usuario) -> PromocionRespuesta:
    """
    Convierte una promoción y sus componentes en el esquema de respuesta. El ahorro del
    cliente es público; el costo y la ganancia del negocio solo se calculan para el ADMINISTRADOR.
    """
    componentes_respuesta = [
        ComponentePromocionRespuesta(
            producto_id=c.producto_id,
            nombre_producto=c.producto.nombre,
            cantidad=c.cantidad,
            imagen_url=c.producto.imagen_url,
        )
        for c in promocion.componentes
    ]

    valor_normal = sum(c.cantidad * c.producto.precio_venta for c in promocion.componentes)
    ahorro_cliente = valor_normal - promocion.precio_promocional
    porcentaje_descuento = round((ahorro_cliente / valor_normal) * 100, 2) if valor_normal > 0 else 0.0

    costo_total = None
    ganancia_negocio = None
    margen_ganancia_porcentaje = None

    if usuario.rol == RolUsuario.ADMINISTRADOR:
        costo = sum(c.cantidad * c.producto.precio_compra for c in promocion.componentes)
        ganancia = promocion.precio_promocional - costo
        margen_ganancia_porcentaje = (
            round((ganancia / promocion.precio_promocional) * 100, 2)
            if promocion.precio_promocional > 0
            else 0.0
        )
        costo_total = round(costo, 2)
        ganancia_negocio = round(ganancia, 2)

    return PromocionRespuesta(
        id=promocion.id,
        nombre=promocion.nombre,
        descripcion=promocion.descripcion,
        precio_promocional=promocion.precio_promocional,
        valor_normal=round(valor_normal, 2),
        ahorro_cliente=round(ahorro_cliente, 2),
        porcentaje_descuento=porcentaje_descuento,
        activa=promocion.activa,
        componentes=componentes_respuesta,
        costo_total=costo_total,
        ganancia_negocio=ganancia_negocio,
        margen_ganancia_porcentaje=margen_ganancia_porcentaje,
    )


def _validar_componentes(db: Session, items: list[ComponentePromocionCrear]) -> None:
    """
    Verifica que ningún producto se repita dentro de la promoción y que todos existan y
    estén activos. Se valida ANTES de modificar nada en la base de datos.
    """
    ids = [item.producto_id for item in items]
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un mismo producto aparece más de una vez en la promoción. Suma sus cantidades en una sola línea.",
        )

    activos = {
        fila[0]
        for fila in db.query(Producto.id).filter(Producto.id.in_(ids), Producto.activo.is_(True)).all()
    }
    faltantes = [producto_id for producto_id in ids if producto_id not in activos]
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con id {faltantes[0]} no encontrado o inactivo",
        )


def _componentes_nuevos(items: list[ComponentePromocionCrear]) -> list[ComponentePromocion]:
    """Crea los componentes de la promoción (la relación completa su promocion_id al guardar)."""
    return [ComponentePromocion(producto_id=item.producto_id, cantidad=item.cantidad) for item in items]


@router.get("/", response_model=list[PromocionRespuesta])
def listar_promociones(
    incluir_inactivas: bool = Query(default=False),
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """
    Lista las promociones activas (las del punto de venta). Si el usuario es administrador
    y envía incluir_inactivas=true, también devuelve las desactivadas para gestionarlas.
    """
    consulta = _consulta_promociones(db)
    if not (incluir_inactivas and usuario.rol == RolUsuario.ADMINISTRADOR):
        consulta = consulta.filter(Promocion.activa.is_(True))

    promociones = consulta.order_by(Promocion.nombre).all()
    return [_construir_respuesta(p, usuario) for p in promociones]


@router.post("/", response_model=PromocionRespuesta, status_code=status.HTTP_201_CREATED)
def crear_promocion(
    request: Request,
    datos: PromocionCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Crea una nueva promoción con sus productos componentes."""
    _validar_componentes(db, datos.items)

    nueva_promocion = Promocion(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        precio_promocional=datos.precio_promocional,
        activa=True,
        componentes=_componentes_nuevos(datos.items),
    )
    db.add(nueva_promocion)
    db.flush()  # Genera el id antes de confirmar
    promocion_id = nueva_promocion.id
    db.commit()

    promocion = _consulta_promociones(db).filter(Promocion.id == promocion_id).one()
    registrar_negocio(
        accion=f"Creó la promoción #{promocion.id} '{promocion.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Precio promocional: {formatear_cop(promocion.precio_promocional)}",
        request=request,
    )
    return _construir_respuesta(promocion, usuario)


@router.put("/{promocion_id}", response_model=PromocionRespuesta)
def actualizar_promocion(
    request: Request,
    promocion_id: int,
    datos: PromocionActualizar,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Actualiza una promoción. Si se envían 'items', reemplaza todos sus componentes."""
    promocion = _consulta_promociones(db).filter(Promocion.id == promocion_id).first()
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada")

    datos_dict = datos.model_dump(exclude_unset=True)
    datos_dict.pop("items", None)
    items = datos.items  # None si no se envió: los componentes no cambian

    if items is not None:
        _validar_componentes(db, items)

    estado_anterior = promocion.activa
    for campo, valor in datos_dict.items():
        setattr(promocion, campo, valor)

    if items is not None:
        # Reemplaza los componentes: los anteriores quedan huérfanos y se borran al guardar
        promocion.componentes.clear()
        promocion.componentes.extend(_componentes_nuevos(items))

    db.commit()
    promocion = _consulta_promociones(db).filter(Promocion.id == promocion_id).one()

    if promocion.activa != estado_anterior:
        accion = "Activó" if promocion.activa else "Desactivó"
    else:
        accion = "Modificó"
    registrar_negocio(
        accion=f"{accion} la promoción #{promocion.id} '{promocion.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Precio promocional: {formatear_cop(promocion.precio_promocional)}",
        request=request,
    )
    return _construir_respuesta(promocion, usuario)


@router.delete("/{promocion_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_promocion(
    request: Request,
    promocion_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Desactiva una promoción (eliminación lógica, conserva el historial de ventas que ya la usaron)."""
    promocion = db.query(Promocion).filter(Promocion.id == promocion_id).first()
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada")

    promocion.activa = False
    db.commit()

    registrar_negocio(
        accion=f"Desactivó la promoción #{promocion.id} '{promocion.nombre}'",
        usuario=usuario.nombre_usuario,
        request=request,
    )