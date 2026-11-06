# Ruta: backend/app/routers/ventas.py
# Endpoints del punto de venta (POS): abrir una venta (rápida o de mesa), agregar y
# quitar productos del carrito, cobrar (uno o varios métodos de pago: factura
# partida), consultar el historial, anular una venta ya cobrada reponiendo el
# inventario, y generar la factura (datos para tirilla, PDF y envío por correo).
#
# CONCURRENCIA (PostgreSQL/Neon): las operaciones que cambian inventario o estado
# bloquean primero la fila de la venta y de los productos (SELECT ... FOR UPDATE).
# Así, dos cajeros que cobran o anulan la misma venta al mismo tiempo no duplican
# el descuento de stock. En SQLite (local) FOR UPDATE se ignora sin problema.
#
# TRAZABILIDAD: las anulaciones quedan en la propia venta y en el log de negocio con
# los productos anulados (los detalles nunca se borran: solo cambia venta.estado).
#
# ZONA HORARIA: fecha_pago y fecha_anulacion usan ahora_colombia() (ver zona_horaria.py).

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, cast, String as TipoString
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_rol, requerir_permiso
from app.logs.logger import registrar_negocio
from app.models.mesa import Mesa, EstadoMesa
from app.models.producto import Producto
from app.models.promocion import Promocion, ComponentePromocion
from app.models.usuario import Usuario, RolUsuario
from app.models.venta import Venta, DetalleVenta, EstadoVenta, MetodoPago, PagoVentaDetalle
from app.schemas.venta import (
    VentaCrear,
    ItemVentaCrear,
    ItemVentaActualizar,
    PagoVenta,
    VentaAnular,
    PromocionVentaCrear,
    VentaRespuesta,
    DetalleVentaRespuesta,
    PagoDetalleRespuesta,
    FacturaEnviarCorreo,
)
from app.utils.calculadora_financiera import resolver_configuracion_efectiva
from app.utils.configuracion_financiera import obtener_configuracion_financiera
from app.utils.envio_correo import enviar_factura_por_correo, ErrorEnvioCorreo
from app.utils.generador_factura import construir_datos_factura, generar_pdf_factura
from app.utils.limitador import limitador
from app.utils.zona_horaria import ahora_colombia

router = APIRouter(prefix="/api/ventas", tags=["Punto de venta"])

# Roles que pueden operar el punto de venta (cobrar, anular, facturar)
_ROLES_POS = (RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)

# Tolerancia para comparar montos en punto flotante (evita rechazar por diferencias de centavos)
_TOLERANCIA_CENTAVOS = 0.01


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _formatear_pesos(valor: float) -> str:
    """Formatea un monto como pesos colombianos (punto de miles), ej. $ 12.500."""
    return "$" + f"{valor:,.0f}".replace(",", ".")


def _construir_respuesta(venta: Venta) -> VentaRespuesta:
    """Convierte una venta con sus detalles y pagos en el esquema de respuesta del frontend."""
    detalles_respuesta = [
        DetalleVentaRespuesta(
            id=detalle.id,
            producto_id=detalle.producto_id,
            nombre_producto=detalle.producto.nombre,
            promocion_id=detalle.promocion_id,
            nombre_promocion=detalle.promocion.nombre if detalle.promocion else None,
            cantidad=detalle.cantidad,
            precio_venta_unitario=detalle.precio_venta_unitario,
            subtotal=detalle.subtotal,
        )
        for detalle in venta.detalles
    ]
    pagos_respuesta = [
        PagoDetalleRespuesta(metodo_pago=pago.metodo_pago, monto=pago.monto)
        for pago in venta.pagos
    ]
    return VentaRespuesta(
        id=venta.id,
        mesa_id=venta.mesa_id,
        estado=venta.estado,
        subtotal=venta.subtotal,
        total=venta.total,
        monto_pagado=venta.monto_pagado,
        cambio=venta.cambio,
        metodo_pago=venta.metodo_pago,
        pagos=pagos_respuesta,
        fecha_apertura=venta.fecha_apertura,
        fecha_pago=venta.fecha_pago,
        detalles=detalles_respuesta,
        nombre_vendedor=venta.usuario.nombre_completo if venta.usuario else None,
        numero_mesa=str(venta.mesa.numero) if venta.mesa_id and venta.mesa else None,
        motivo_anulacion=venta.motivo_anulacion,
        nombre_usuario_anulacion=venta.usuario_anulacion.nombre_completo if venta.usuario_anulacion else None,
        fecha_anulacion=venta.fecha_anulacion,
    )


def _recalcular_totales(venta: Venta) -> None:
    """Recalcula subtotal y total sumando el subtotal de cada producto del carrito."""
    venta.subtotal = round(sum(detalle.subtotal for detalle in venta.detalles), 2)
    venta.total = venta.subtotal


def _consulta_venta_completa(db: Session):
    """Consulta base con todas las relaciones necesarias para construir VentaRespuesta."""
    return db.query(Venta).options(
        joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
        joinedload(Venta.mesa),
        joinedload(Venta.usuario),
        joinedload(Venta.usuario_anulacion),
        joinedload(Venta.pagos),
    )


def _bloquear_venta(db: Session, venta_id: int) -> None:
    """
    Bloquea la fila de la venta hasta terminar la transacción. Si otra petición la
    tiene bloqueada, esta espera. Se hace en una consulta simple, sin uniones, porque
    PostgreSQL no permite FOR UPDATE sobre el lado nulo de un LEFT JOIN.
    """
    db.query(Venta.id).filter(Venta.id == venta_id).with_for_update().first()


def _bloquear_productos(db: Session, producto_ids) -> dict[int, Producto]:
    """
    Bloquea los productos indicados (siempre en orden de id, para evitar bloqueos
    cruzados entre dos cobros) y los devuelve en un diccionario por id.
    """
    ids = sorted(set(producto_ids))
    if not ids:
        return {}
    productos = (
        db.query(Producto)
        .filter(Producto.id.in_(ids))
        .order_by(Producto.id)
        .with_for_update()
        .all()
    )
    return {producto.id: producto for producto in productos}


def _cantidades_por_producto(venta: Venta) -> dict[int, int]:
    """Suma las cantidades por producto (un mismo producto puede estar normal y en promoción)."""
    cantidades: dict[int, int] = {}
    for detalle in venta.detalles:
        cantidades[detalle.producto_id] = cantidades.get(detalle.producto_id, 0) + detalle.cantidad
    return cantidades


def _obtener_venta_abierta_o_error(venta_id: int, db: Session) -> Venta:
    """Busca la venta (bloqueándola) y exige que siga abierta."""
    _bloquear_venta(db, venta_id)
    venta = _consulta_venta_completa(db).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado != EstadoVenta.ABIERTA:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta venta ya fue cerrada")
    return venta


def _obtener_venta_pagada_o_error(venta_id: int, db: Session) -> Venta:
    """Busca la venta (bloqueándola) y exige que esté PAGADA (única que se puede anular)."""
    _bloquear_venta(db, venta_id)
    venta = _consulta_venta_completa(db).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado != EstadoVenta.PAGADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden anular ventas que estén cobradas (pagadas).",
        )
    return venta


def _obtener_venta_facturable_o_error(venta_id: int, db: Session) -> Venta:
    """
    Busca una venta ya cobrada (con fecha de pago). Se factura tanto una venta PAGADA
    como una ANULADA (el cliente conserva un comprobante), nunca un carrito abierto
    ni uno cancelado antes de cobrarse.
    """
    venta = _consulta_venta_completa(db).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.fecha_pago is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta venta todavía no ha sido cobrada, no se puede generar una factura.",
        )
    return venta


# =============================================================================
# CONSULTAS
# =============================================================================

@router.get("/abiertas", response_model=list[VentaRespuesta])
def listar_ventas_abiertas(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Lista las ventas que siguen abiertas (carritos en construcción), útil para reanudar mesas."""
    ventas = _consulta_venta_completa(db).filter(Venta.estado == EstadoVenta.ABIERTA).all()
    return [_construir_respuesta(v) for v in ventas]


@router.get("/historial/recientes", response_model=list[VentaRespuesta])
def listar_historial_ventas(
    busqueda: str | None = Query(default=None, max_length=60),
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Lista las ventas cerradas (pagadas o anuladas) más recientes. Admite buscar por
    número de venta, número de mesa o nombre del vendedor.
    """
    consulta = _consulta_venta_completa(db).filter(
        Venta.estado.in_([EstadoVenta.PAGADA, EstadoVenta.ANULADA])
    )

    if busqueda:
        texto = busqueda.strip()
        # autoescape: un "%" o "_" escrito por el usuario se busca como texto, no como comodín
        consulta = (
            consulta.outerjoin(Mesa, Venta.mesa_id == Mesa.id)
            .join(Usuario, Venta.usuario_id == Usuario.id)
            .filter(
                or_(
                    Mesa.numero.icontains(texto, autoescape=True),
                    Usuario.nombre_completo.icontains(texto, autoescape=True),
                    cast(Venta.id, TipoString).icontains(texto, autoescape=True),
                )
            )
        )

    ventas = consulta.order_by(Venta.fecha_pago.desc()).limit(limite).all()
    return [_construir_respuesta(v) for v in ventas]


@router.get("/{venta_id}", response_model=VentaRespuesta)
def obtener_venta(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Obtiene el detalle completo de una venta, esté abierta, pagada, anulada o cancelada."""
    venta = _consulta_venta_completa(db).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return _construir_respuesta(venta)


# =============================================================================
# CARRITO
# =============================================================================

@router.post("/", response_model=VentaRespuesta, status_code=status.HTTP_201_CREATED)
def abrir_venta(
    datos: VentaCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Abre una nueva venta. Con mesa_id, la mesa debe estar libre y pasa a 'ocupada'
    (se bloquea la fila de la mesa para que dos meseros no la abran a la vez).
    Sin mesa_id es una venta rápida.
    """
    if datos.mesa_id is not None:
        mesa = db.query(Mesa).filter(Mesa.id == datos.mesa_id).with_for_update().first()
        if not mesa:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa no encontrada")
        if mesa.estado != EstadoMesa.LIBRE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La mesa seleccionada no está libre")
        mesa.estado = EstadoMesa.OCUPADA

    nueva_venta = Venta(mesa_id=datos.mesa_id, usuario_id=usuario.id, estado=EstadoVenta.ABIERTA)
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)
    return _construir_respuesta(nueva_venta)


@router.post("/{venta_id}/items", response_model=VentaRespuesta)
def agregar_producto_a_venta(
    venta_id: int,
    datos: ItemVentaCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Agrega un producto al carrito (o suma cantidad si ya estaba). Congela en la línea
    el impuesto que aplica en este momento, para que la factura nunca cambie después.
    """
    configuracion_global = obtener_configuracion_financiera(db)
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    producto = db.query(Producto).filter(Producto.id == datos.producto_id, Producto.activo.is_(True)).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    detalle_existente = next(
        (d for d in venta.detalles if d.producto_id == producto.id and d.promocion_id is None), None
    )
    if detalle_existente:
        detalle_existente.cantidad += datos.cantidad
    else:
        config_efectiva = resolver_configuracion_efectiva(producto, configuracion_global)
        nuevo_detalle = DetalleVenta(
            venta_id=venta.id,
            producto_id=producto.id,
            cantidad=datos.cantidad,
            precio_venta_unitario=producto.precio_venta,
            precio_compra_unitario=producto.precio_compra,
            tipo_impuesto_aplicado=config_efectiva.tipo_impuesto,
            porcentaje_impuesto_aplicado=config_efectiva.porcentaje_impuesto,
            etiqueta_impuesto_aplicado=config_efectiva.etiqueta_impuesto,
        )
        db.add(nuevo_detalle)
        venta.detalles.append(nuevo_detalle)

    _recalcular_totales(venta)
    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


@router.post("/{venta_id}/promociones", response_model=VentaRespuesta)
def agregar_promocion_a_venta(
    venta_id: int,
    datos: PromocionVentaCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Agrega una promoción (combo) al carrito. El precio especial se reparte
    proporcionalmente entre sus productos, y cada uno congela su propio impuesto.
    """
    configuracion_global = obtener_configuracion_financiera(db)
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    promocion = (
        db.query(Promocion)
        .options(joinedload(Promocion.componentes).joinedload(ComponentePromocion.producto))
        .filter(Promocion.id == datos.promocion_id, Promocion.activa.is_(True))
        .first()
    )
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada o inactiva")

    valor_normal_total = sum(c.cantidad * c.producto.precio_venta for c in promocion.componentes)
    factor_descuento = (promocion.precio_promocional / valor_normal_total) if valor_normal_total > 0 else 1

    for componente in promocion.componentes:
        cantidad_total = componente.cantidad * datos.cantidad
        precio_unitario_con_descuento = round(componente.producto.precio_venta * factor_descuento, 2)

        detalle_existente = next(
            (d for d in venta.detalles if d.producto_id == componente.producto_id and d.promocion_id == promocion.id),
            None,
        )
        if detalle_existente:
            detalle_existente.cantidad += cantidad_total
        else:
            config_efectiva = resolver_configuracion_efectiva(componente.producto, configuracion_global)
            nuevo_detalle = DetalleVenta(
                venta_id=venta.id,
                producto_id=componente.producto_id,
                promocion_id=promocion.id,
                cantidad=cantidad_total,
                precio_venta_unitario=precio_unitario_con_descuento,
                precio_compra_unitario=componente.producto.precio_compra,
                tipo_impuesto_aplicado=config_efectiva.tipo_impuesto,
                porcentaje_impuesto_aplicado=config_efectiva.porcentaje_impuesto,
                etiqueta_impuesto_aplicado=config_efectiva.etiqueta_impuesto,
            )
            db.add(nuevo_detalle)
            venta.detalles.append(nuevo_detalle)

    _recalcular_totales(venta)
    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


@router.put("/{venta_id}/items/{detalle_id}", response_model=VentaRespuesta)
def actualizar_cantidad_item(
    venta_id: int,
    detalle_id: int,
    datos: ItemVentaActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Modifica la cantidad de un producto ya agregado al carrito de una venta abierta."""
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    detalle = next((d for d in venta.detalles if d.id == detalle_id), None)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado en el carrito")

    detalle.cantidad = datos.cantidad
    _recalcular_totales(venta)
    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


@router.delete("/{venta_id}/items/{detalle_id}", response_model=VentaRespuesta)
def eliminar_item_de_venta(
    venta_id: int,
    detalle_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Elimina un producto del carrito de una venta abierta."""
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    detalle = next((d for d in venta.detalles if d.id == detalle_id), None)
    if not detalle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado en el carrito")

    venta.detalles.remove(detalle)
    db.delete(detalle)
    _recalcular_totales(venta)
    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


@router.post("/{venta_id}/marcar-pendiente-pago", response_model=VentaRespuesta)
def marcar_mesa_pendiente_pago(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Marca la mesa asociada como 'pendiente de pago' (el cliente pidió la cuenta)."""
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    if venta.mesa_id:
        mesa = db.query(Mesa).filter(Mesa.id == venta.mesa_id).first()
        if mesa:
            mesa.estado = EstadoMesa.PENDIENTE_PAGO

    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


# =============================================================================
# COBRO, ANULACIÓN Y CANCELACIÓN
# =============================================================================

@router.post("/{venta_id}/pagar", response_model=VentaRespuesta)
def pagar_venta(
    venta_id: int,
    datos: PagoVenta,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Cobra una venta abierta: valida que el carrito no esté vacío y que la suma de
    los pagos (uno o varios métodos) alcance el total. Descuenta el inventario,
    calcula el cambio y guarda un registro por cada método usado. Con un solo método,
    Venta.metodo_pago queda con ese método; con dos o más, queda como MIXTO.
    """
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    if not venta.detalles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cobrar una venta sin productos")

    _recalcular_totales(venta)

    monto_total_pagado = round(sum(pago.monto for pago in datos.pagos), 2)
    if monto_total_pagado + _TOLERANCIA_CENTAVOS < venta.total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La suma de los pagos es menor al total de la venta",
        )

    # Bloque: valida el stock con la cantidad TOTAL por producto (ya con los productos bloqueados)
    cantidades = _cantidades_por_producto(venta)
    productos = _bloquear_productos(db, cantidades)
    for producto_id, cantidad in cantidades.items():
        producto = productos.get(producto_id)
        if producto is None or producto.stock_actual < cantidad:
            nombre = producto.nombre if producto else f"#{producto_id}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{nombre}'",
            )

    # Bloque: descuenta el inventario
    for producto_id, cantidad in cantidades.items():
        productos[producto_id].stock_actual -= cantidad

    # Bloque: un registro de pago por cada método recibido (factura partida si hay más de uno)
    venta.pagos.clear()
    for pago in datos.pagos:
        venta.pagos.append(PagoVentaDetalle(metodo_pago=pago.metodo_pago, monto=round(pago.monto, 2)))

    venta.metodo_pago = datos.pagos[0].metodo_pago if len(datos.pagos) == 1 else MetodoPago.MIXTO
    venta.monto_pagado = monto_total_pagado
    venta.cambio = round(max(monto_total_pagado - venta.total, 0), 2)
    venta.estado = EstadoVenta.PAGADA
    venta.fecha_pago = ahora_colombia()

    if venta.mesa_id:
        mesa = db.query(Mesa).filter(Mesa.id == venta.mesa_id).first()
        if mesa:
            mesa.estado = EstadoMesa.LIBRE

    db.commit()
    db.refresh(venta)
    return _construir_respuesta(venta)


@router.post("/{venta_id}/anular", response_model=VentaRespuesta)
def anular_venta_pagada(
    venta_id: int,
    datos: VentaAnular,
    request: Request,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("ventas_anular")),
):
    """
    Anula una venta que YA estaba cobrada: repone el stock de cada producto, cambia
    el estado a ANULADA (el registro y sus productos se conservan) y guarda quién
    la anuló, cuándo y el motivo obligatorio, en la venta y en el log de negocio.
    """
    venta = _obtener_venta_pagada_o_error(venta_id, db)

    cantidades = _cantidades_por_producto(venta)
    productos = _bloquear_productos(db, cantidades)
    for producto_id, cantidad in cantidades.items():
        if producto_id in productos:
            productos[producto_id].stock_actual += cantidad

    motivo_limpio = datos.motivo.strip()

    venta.estado = EstadoVenta.ANULADA
    venta.motivo_anulacion = motivo_limpio
    venta.usuario_anulacion_id = usuario.id
    venta.fecha_anulacion = ahora_colombia()

    db.commit()
    db.refresh(venta)

    # Listado legible de productos anulados, ej: "2x Cerveza, 1x Papas"
    productos_anulados_texto = ", ".join(
        f"{detalle.cantidad}x {detalle.producto.nombre}"
        for detalle in venta.detalles
        if detalle.producto
    ) or "sin productos registrados"

    referencia_venta = f"Mesa {venta.mesa.numero}" if venta.mesa_id and venta.mesa else "Venta rápida"
    registrar_negocio(
        accion=f"Anuló la venta cobrada #{venta.id} ({referencia_venta})",
        usuario=usuario.nombre_usuario,
        detalle=(
            f"Total: {_formatear_pesos(venta.total)} | Productos anulados: {productos_anulados_texto} "
            f"| Motivo: {motivo_limpio}"
        ),
        request=request,
    )

    return _construir_respuesta(venta)


@router.delete("/{venta_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_venta(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Cancela una venta abierta (carrito SIN cobrar) sin afectar el inventario y libera la mesa."""
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    venta.estado = EstadoVenta.CANCELADA

    if venta.mesa_id:
        mesa = db.query(Mesa).filter(Mesa.id == venta.mesa_id).first()
        if mesa:
            mesa.estado = EstadoMesa.LIBRE

    db.commit()


# =============================================================================
# FACTURACIÓN: tirilla (datos JSON), descarga en PDF y envío por correo
# =============================================================================

@router.get("/{venta_id}/factura", tags=["Facturación"])
def obtener_datos_factura(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Devuelve los datos de la factura de una venta cobrada, listos para imprimir una tirilla."""
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    return construir_datos_factura(venta)


@router.get("/{venta_id}/factura/pdf", tags=["Facturación"])
def descargar_factura_pdf(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """Genera y descarga la factura de una venta cobrada en formato PDF."""
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    archivo = generar_pdf_factura(construir_datos_factura(venta))

    return StreamingResponse(
        archivo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="factura_{venta.id}.pdf"'},
    )


@router.post("/{venta_id}/factura/enviar-correo", tags=["Facturación"])
@limitador.limit("5/minute")
def enviar_factura_correo(
    request: Request,
    venta_id: int,
    datos_correo: FacturaEnviarCorreo,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Envía la factura de una venta cobrada al correo indicado, con el PDF adjunto.
    Limitado a 5 envíos por minuto por IP (evita usar el servidor de correo para spam).
    Queda registrado en el log de negocio quién la envió y a qué correo.
    """
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    archivo_pdf = generar_pdf_factura(construir_datos_factura(venta))

    try:
        enviar_factura_por_correo(
            destinatario=datos_correo.correo,
            pdf_bytes=archivo_pdf.getvalue(),
            nombre_archivo=f"factura_{venta.id}.pdf",
            numero_venta=venta.id,
        )
    except ErrorEnvioCorreo as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error))

    registrar_negocio(
        accion=f"Envió por correo la factura de la venta #{venta.id}",
        usuario=usuario.nombre_usuario,
        detalle=f"Destinatario: {datos_correo.correo}",
        request=request,
    )

    return {"detalle": f"Factura enviada correctamente a {datos_correo.correo}."}