# Ruta: backend/app/routers/promociones.py
# Endpoints para crear, listar, actualizar y desactivar promociones (combos de
# productos vendidos a un precio especial, ej: "2 cervezas + snack").
#
# SEGURIDAD (datos financieros sensibles): el costo de un producto
# (precio_compra) nunca debe llegar a un usuario con rol EMPLEADO, porque
# revela el margen de utilidad del negocio. _construir_respuesta() solo
# calcula "costo_total", "ganancia_negocio" y "margen_ganancia_porcentaje"
# cuando quien consulta es ADMINISTRADOR; para los demás quedan en None.
#
# CAMBIOS EN ESTA VERSIÓN:
# - GET admite ?incluir_inactivas=true (solo lo respeta para el administrador),
#   necesario para poder volver a activar una promoción desactivada.
# - Se rechazan productos repetidos dentro de una misma promoción y los
#   valores nulos en campos obligatorios al editar (antes daban error 500).
# - Crear, editar y activar/desactivar quedan registrados en negocio.log.

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

router = APIRouter(prefix="/api/promociones", tags=["Promociones"])


def _construir_respuesta(promocion: Promocion, usuario: Usuario) -> PromocionRespuesta:
    """
    Convierte una promoción y sus componentes en el esquema de respuesta.
    El ahorro del cliente es público para cualquier rol; el costo y la ganancia
    del negocio solo se calculan para el ADMINISTRADOR.
    """
    incluir_datos_sensibles = usuario.rol == RolUsuario.ADMINISTRADOR

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

    if incluir_datos_sensibles:
        costo_total = sum(c.cantidad * c.producto.precio_compra for c in promocion.componentes)
        ganancia_negocio = promocion.precio_promocional - costo_total
        margen_ganancia_porcentaje = (
            round((ganancia_negocio / promocion.precio_promocional) * 100, 2)
            if promocion.precio_promocional > 0
            else 0.0
        )
        costo_total = round(costo_total, 2)
        ganancia_negocio = round(ganancia_negocio, 2)

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
    Verifica que ningún producto se repita dentro de la promoción y que todos
    existan y estén activos. Se valida ANTES de modificar nada en la base de datos.
    """
    ids = [item.producto_id for item in items]
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un mismo producto aparece más de una vez en la promoción. Suma sus cantidades en una sola línea.",
        )
    for producto_id in ids:
        existe = db.query(Producto.id).filter(Producto.id == producto_id, Producto.activo.is_(True)).first()
        if not existe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con id {producto_id} no encontrado o inactivo",
            )


@router.get("/", response_model=list[PromocionRespuesta])
def listar_promociones(
    incluir_inactivas: bool = Query(default=False),
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """
    Lista las promociones activas (las usadas en el punto de venta). Si el
    usuario es administrador y envía incluir_inactivas=true, también devuelve
    las desactivadas para poder gestionarlas.
    """
    consulta = db.query(Promocion).options(
        joinedload(Promocion.componentes).joinedload(ComponentePromocion.producto)
    )
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
    )
    db.add(nueva_promocion)
    db.flush()

    for item in datos.items:
        db.add(ComponentePromocion(promocion_id=nueva_promocion.id, producto_id=item.producto_id, cantidad=item.cantidad))

    db.commit()
    db.refresh(nueva_promocion)

    registrar_negocio(
        accion=f"Creó la promoción #{nueva_promocion.id} '{nueva_promocion.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Precio promocional: ${nueva_promocion.precio_promocional:,.0f}",
        request=request,
    )
    return _construir_respuesta(nueva_promocion, usuario)


@router.put("/{promocion_id}", response_model=PromocionRespuesta)
def actualizar_promocion(
    request: Request,
    promocion_id: int,
    datos: PromocionActualizar,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Actualiza una promoción. Si se envían 'items', reemplaza todos sus componentes."""
    promocion = db.query(Promocion).filter(Promocion.id == promocion_id).first()
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada")

    datos_dict = datos.model_dump(exclude_unset=True)
    datos_dict.pop("items", None)
    items = datos.items  # None si no se envió: los componentes no cambian

    # Los campos obligatorios no pueden quedar en nulo (la base de datos no lo admite)
    for campo in ("nombre", "precio_promocional", "activa"):
        if campo in datos_dict and datos_dict[campo] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El campo '{campo}' no puede quedar vacío")

    if items is not None:
        if not items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La promoción debe tener al menos un producto")
        _validar_componentes(db, items)

    estado_anterior = promocion.activa
    for campo, valor in datos_dict.items():
        setattr(promocion, campo, valor)

    if items is not None:
        # Elimina los componentes anteriores y registra los nuevos
        for componente in list(promocion.componentes):
            db.delete(componente)
        db.flush()
        for item in items:
            db.add(ComponentePromocion(promocion_id=promocion.id, producto_id=item.producto_id, cantidad=item.cantidad))

    db.commit()
    db.refresh(promocion)

    if promocion.activa != estado_anterior:
        accion = "Activó" if promocion.activa else "Desactivó"
    else:
        accion = "Modificó"
    registrar_negocio(
        accion=f"{accion} la promoción #{promocion.id} '{promocion.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Precio promocional: ${promocion.precio_promocional:,.0f}",
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