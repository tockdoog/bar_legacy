# Ruta: backend/app/routers/promociones.py
# Endpoints para crear, listar, actualizar y desactivar promociones (combos de
# productos vendidos a un precio especial, ej: "2 cervezas + snack").
#
# SEGURIDAD (datos financieros sensibles): el costo de un producto
# (precio_compra) nunca debe llegar a un usuario con rol EMPLEADO, porque
# revela el margen de utilidad del negocio. Por eso _construir_respuesta()
# recibe el usuario que hace la petición y solo calcula/adjunta
# "costo_total", "ganancia_negocio" y "margen_ganancia_porcentaje" cuando
# ese usuario es ADMINISTRADOR. Para EMPLEADO, esos tres campos quedan en
# None y el frontend los oculta.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.producto import Producto
from app.models.promocion import Promocion, ComponentePromocion
from app.models.usuario import RolUsuario, Usuario
from app.schemas.promocion import (
    PromocionCrear,
    PromocionActualizar,
    PromocionRespuesta,
    ComponentePromocionRespuesta,
)

router = APIRouter(prefix="/api/promociones", tags=["Promociones"])


def _construir_respuesta(promocion: Promocion, usuario: Usuario) -> PromocionRespuesta:
    """
    Convierte una promoción y sus componentes en el esquema de respuesta.

    Calcula siempre el ahorro del cliente (dato público para cualquier rol
    autenticado). Calcula el costo y la ganancia del negocio SOLO si quien
    consulta es ADMINISTRADOR; para cualquier otro rol esos campos se
    devuelven en None, sin excepción, sin importar qué endpoint llame a
    esta función.
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


@router.get("/", response_model=list[PromocionRespuesta])
def listar_promociones(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista todas las promociones activas (visibles para usar en el punto de venta)."""
    promociones = (
        db.query(Promocion)
        .options(joinedload(Promocion.componentes).joinedload(ComponentePromocion.producto))
        .filter(Promocion.activa.is_(True))
        .all()
    )
    return [_construir_respuesta(p, usuario) for p in promociones]


@router.post("/", response_model=PromocionRespuesta, status_code=status.HTTP_201_CREATED)
def crear_promocion(
    datos: PromocionCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Crea una nueva promoción con sus productos componentes."""
    for item in datos.items:
        if not db.query(Producto).filter(Producto.id == item.producto_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Producto con id {item.producto_id} no encontrado")

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
    return _construir_respuesta(nueva_promocion, usuario)


@router.put("/{promocion_id}", response_model=PromocionRespuesta)
def actualizar_promocion(
    promocion_id: int,
    datos: PromocionActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Actualiza los datos de una promoción. Si se envían 'items', reemplaza todos sus componentes."""
    promocion = db.query(Promocion).filter(Promocion.id == promocion_id).first()
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada")

    datos_dict = datos.model_dump(exclude_unset=True)
    items = datos_dict.pop("items", None)

    for campo, valor in datos_dict.items():
        setattr(promocion, campo, valor)

    if items is not None:
        # Elimina los componentes anteriores y registra los nuevos
        for componente in list(promocion.componentes):
            db.delete(componente)
        db.flush()
        for item in items:
            if not db.query(Producto).filter(Producto.id == item["producto_id"]).first():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Producto con id {item['producto_id']} no encontrado")
            db.add(ComponentePromocion(promocion_id=promocion.id, producto_id=item["producto_id"], cantidad=item["cantidad"]))

    db.commit()
    db.refresh(promocion)
    return _construir_respuesta(promocion, usuario)


@router.delete("/{promocion_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_promocion(
    promocion_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Desactiva una promoción (eliminación lógica, conserva el historial de ventas que ya la usaron)."""
    promocion = db.query(Promocion).filter(Promocion.id == promocion_id).first()
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada")

    promocion.activa = False
    db.commit()