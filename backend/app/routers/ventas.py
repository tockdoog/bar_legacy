# Ruta: backend/app/routers/ventas.py
# Endpoints del punto de venta (POS): abrir una venta (rápida o de mesa), agregar
# y quitar productos del carrito, cobrar (con uno o varios métodos de pago:
# factura partida), consultar el historial de ventas cobradas/anuladas para
# buscarlas, anular una venta que YA estaba cobrada reponiendo automáticamente
# el inventario, y generar la factura de una venta ya cobrada en tres
# modalidades: datos para imprimir una tirilla desde el navegador, descarga en
# PDF, y envío del PDF por correo electrónico al cliente.
#
# TRAZABILIDAD DE ANULACIONES: cuando se anula una venta ya cobrada, además de
# quedar registrado en la propia venta (motivo, quién y cuándo, consultable
# desde "Ventas cobradas" en el POS), se registra en logs/negocio.log un
# resumen legible con los PRODUCTOS anulados (no solo el total), para que el
# panel de Monitoreo (logs.html) muestre exactamente qué se anuló. Los
# reportes (reportes.html) también pueden listar estas anulaciones porque los
# detalles de productos NUNCA se borran al anular: solo cambia venta.estado.
#
# ZONA HORARIA: fecha_pago y fecha_anulacion se guardan con ahora_colombia()
# (hora local de Colombia, "naive"), NUNCA con datetime.now(timezone.utc).
# Ver app/utils/zona_horaria.py para el detalle de por qué: SQLite no
# conserva tzinfo, y mezclar UTC (al guardar) con hora del servidor (al
# filtrar reportes) hacía que una venta apareciera fechada un día después.

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, cast, String as TipoString
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_rol, requerir_permiso, obtener_usuario_actual
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

from app.models.finanzas import ConfiguracionFinanciera, TipoImpuesto
from app.utils.calculadora_financiera import resolver_configuracion_efectiva
from app.utils.zona_horaria import ahora_colombia

from app.utils.generador_factura import construir_datos_factura, generar_pdf_factura
from app.utils.envio_correo import enviar_factura_por_correo, ErrorEnvioCorreo
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/ventas", tags=["Punto de venta"])

# Roles que pueden operar el punto de venta, incluyendo cobrar, anular ventas
# y generar/enviar facturas.
_ROLES_POS = (RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)

# Margen de tolerancia para comparar montos en punto flotante (evita rechazar
# un pago por diferencias de centavos por redondeo, ej. 19999.999999999996)
_TOLERANCIA_CENTAVOS = 0.01


def _construir_respuesta(venta: Venta) -> VentaRespuesta:
    """Convierte una venta y sus detalles/pagos en el esquema de respuesta para el frontend."""
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
    """Recalcula el subtotal y total de la venta sumando el subtotal de cada producto del carrito."""
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


def _obtener_venta_abierta_o_error(venta_id: int, db: Session) -> Venta:
    """Busca una venta por id, exigiendo que exista y siga abierta (no pagada, ni anulada, ni cancelada)."""
    venta = _consulta_venta_completa(db).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if venta.estado != EstadoVenta.ABIERTA:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta venta ya fue cerrada")
    return venta


def _obtener_venta_pagada_o_error(venta_id: int, db: Session) -> Venta:
    """Busca una venta por id, exigiendo que esté en estado PAGADA (única que se puede anular)."""
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
    Busca una venta por id, exigiendo que ya haya sido cobrada (tiene fecha
    de pago registrada). Se permite facturar tanto ventas PAGADAS como
    ANULADAS (para que el cliente conserve un comprobante de lo ocurrido),
    pero nunca una venta que sigue como carrito abierto o que se canceló
    antes de cobrarse.
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
    Lista las ventas ya cerradas (pagadas o anuladas) más recientes, para que
    el cajero pueda encontrar una venta reciente y anularla si el cliente se
    arrepintió después de que la factura ya se generó. Admite buscar por
    número de venta, número de mesa o nombre del vendedor.
    """
    consulta = _consulta_venta_completa(db).filter(
        Venta.estado.in_([EstadoVenta.PAGADA, EstadoVenta.ANULADA])
    )

    if busqueda:
        texto_busqueda = f"%{busqueda.strip()}%"
        consulta = (
            consulta.outerjoin(Mesa, Venta.mesa_id == Mesa.id)
            .join(Usuario, Venta.usuario_id == Usuario.id)
            .filter(
                or_(
                    Mesa.numero.ilike(texto_busqueda),
                    Usuario.nombre_completo.ilike(texto_busqueda),
                    cast(Venta.id, TipoString).ilike(texto_busqueda),
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


@router.post("/", response_model=VentaRespuesta, status_code=status.HTTP_201_CREATED)
def abrir_venta(
    datos: VentaCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Abre una nueva venta: si se indica mesa_id, la mesa debe estar libre y pasa a
    'ocupada'. Si no se indica, es una venta rápida (sin mesa asociada).
    """
    mesa = None
    if datos.mesa_id is not None:
        mesa = db.query(Mesa).filter(Mesa.id == datos.mesa_id).first()
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

def _obtener_configuracion_financiera(db: Session) -> ConfiguracionFinanciera:
    """
    Devuelve la configuración financiera global (id=1), creándola con
    valores por defecto si aún no existe. Se usa aquí solo para resolver qué
    impuesto congelar en cada línea de venta al momento de cobrar/agregar.
    """
    configuracion = db.query(ConfiguracionFinanciera).filter(ConfiguracionFinanciera.id == 1).first()
    if configuracion is None:
        configuracion = ConfiguracionFinanciera(
            id=1,
            tipo_impuesto=TipoImpuesto.SIN_IMPUESTO,
            porcentaje_impuesto=0.0,
            margen_utilidad_deseado=30.0,
            margen_minimo_saludable=15.0,
        )
        db.add(configuracion)
        db.commit()
        db.refresh(configuracion)
    return configuracion


@router.post("/{venta_id}/items", response_model=VentaRespuesta)
def agregar_producto_a_venta(
    venta_id: int,
    datos: ItemVentaCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Agrega un producto al carrito de una venta abierta (o suma cantidad si
    ya estaba). Congela en la línea qué impuesto aplica a este producto EN
    ESTE MOMENTO (propio del producto o heredado de la configuración
    global), para que la factura de esta venta nunca cambie si más adelante
    se edita el impuesto del producto o la configuración global.
    """
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    producto = db.query(Producto).filter(Producto.id == datos.producto_id, Producto.activo.is_(True)).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    detalle_existente = next((d for d in venta.detalles if d.producto_id == producto.id), None)
    if detalle_existente:
        detalle_existente.cantidad += datos.cantidad
    else:
        configuracion_global = _obtener_configuracion_financiera(db)
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
    Agrega una promoción (combo de productos) al carrito de una venta
    abierta. El precio especial de la promoción se reparte proporcionalmente
    entre sus productos componentes, y cada uno congela SU PROPIO impuesto
    (propio del producto, o heredado de la configuración global) al momento
    de agregarse, igual que un producto individual.
    """
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    promocion = (
        db.query(Promocion)
        .options(joinedload(Promocion.componentes).joinedload(ComponentePromocion.producto))
        .filter(Promocion.id == datos.promocion_id, Promocion.activa.is_(True))
        .first()
    )
    if not promocion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoción no encontrada o inactiva")

    configuracion_global = _obtener_configuracion_financiera(db)
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


@router.post("/{venta_id}/pagar", response_model=VentaRespuesta)
def pagar_venta(
    venta_id: int,
    datos: PagoVenta,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Cobra una venta abierta: valida que el carrito no esté vacío y que la
    suma de todos los pagos recibidos (uno o varios métodos, para soportar
    factura partida) alcance el total. Descuenta el inventario de cada
    producto, calcula el cambio y guarda un registro por cada método de pago
    usado en la tabla pagos_venta. Si se usó un solo método, Venta.metodo_pago
    queda con ese método; si se usaron dos o más, queda como MIXTO (la mezcla
    exacta se consulta en el desglose "pagos" de la respuesta). Tras cobrarse,
    el frontend puede llamar a los endpoints de facturación de más abajo para
    imprimir una tirilla, descargar el PDF o enviarlo por correo.
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

    for detalle in venta.detalles:
        producto = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
        if not producto or producto.stock_actual < detalle.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{detalle.producto.nombre}'",
            )

    for detalle in venta.detalles:
        producto = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
        producto.stock_actual -= detalle.cantidad

    # Guarda un registro de pago por cada método recibido (factura partida
    # cuando hay más de uno). Se limpian pagos previos por seguridad, aunque
    # en la práctica una venta ABIERTA nunca debería tener pagos todavía.
    venta.pagos.clear()
    for pago in datos.pagos:
        venta.pagos.append(PagoVentaDetalle(metodo_pago=pago.metodo_pago, monto=round(pago.monto, 2)))

    # "metodo_pago" queda como resumen: el único método si solo hubo uno, o
    # MIXTO si la venta se cobró con una factura partida (dos o más métodos)
    venta.metodo_pago = datos.pagos[0].metodo_pago if len(datos.pagos) == 1 else MetodoPago.MIXTO

    venta.monto_pagado = monto_total_pagado
    venta.cambio = round(max(monto_total_pagado - venta.total, 0), 2)
    venta.estado = EstadoVenta.PAGADA
    # Hora LOCAL de Colombia (naive), no UTC. Ver zona_horaria.py.
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
    Anula una venta que YA estaba cobrada (ej: el cliente pidió algo y luego
    cambió de opinión después de que la factura se generó). A diferencia de
    cancelar_venta (que es solo para carritos abiertos sin cobrar), esta
    operación:
      1. Repone automáticamente el stock de cada producto de la venta.
      2. Cambia el estado a ANULADA (no se borra el registro ni sus
         productos: quedan visibles en el historial del POS, en los reportes
         y en los logs para trazabilidad completa).
      3. Guarda quién la anuló (usuario autenticado), cuándo, y el motivo
         obligatorio recibido en el cuerpo de la petición -tanto en la propia
         venta como en logs/negocio.log a través de registrar_negocio(). El
         mensaje de log incluye explícitamente la lista de productos
         anulados (no solo el total), para que el panel de Monitoreo
         (logs.html) muestre de un vistazo qué se anuló, cuándo, quién y por qué.
    """
    venta = _obtener_venta_pagada_o_error(venta_id, db)

    for detalle in venta.detalles:
        producto = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
        if producto:
            producto.stock_actual += detalle.cantidad

    motivo_limpio = datos.motivo.strip()

    venta.estado = EstadoVenta.ANULADA
    venta.motivo_anulacion = motivo_limpio
    venta.usuario_anulacion_id = usuario.id
    # Hora LOCAL de Colombia (naive), no UTC. Ver zona_horaria.py.
    venta.fecha_anulacion = ahora_colombia()

    db.commit()
    db.refresh(venta)

    # Construye el listado legible de productos anulados, ej: "2x Cerveza, 1x Papas"
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
            f"Total: ${venta.total:,.0f} | Productos anulados: {productos_anulados_texto} "
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
    """Cancela una venta abierta (carrito SIN cobrar) sin afectar el inventario y libera la mesa asociada."""
    venta = _obtener_venta_abierta_o_error(venta_id, db)

    venta.estado = EstadoVenta.CANCELADA

    if venta.mesa_id:
        mesa = db.query(Mesa).filter(Mesa.id == venta.mesa_id).first()
        if mesa:
            mesa.estado = EstadoMesa.LIBRE

    db.commit()


# =====================================================================
# FACTURACIÓN: tirilla (datos JSON), descarga en PDF y envío por correo
# de la factura de una venta ya cobrada. No aplica a carritos abiertos
# ni a ventas canceladas antes de cobrarse (ver _obtener_venta_facturable_o_error).
# =====================================================================

@router.get("/{venta_id}/factura", tags=["Facturación"])
def obtener_datos_factura(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Devuelve los datos estructurados de la factura de una venta ya cobrada,
    listos para que el frontend imprima una tirilla desde el navegador
    (window.print()), incluyendo la discriminación del impuesto (agrupada
    por tipo) ya congelada en cada línea de venta. No genera ningún archivo:
    es solo la información.
    """
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    return construir_datos_factura(venta)


@router.get("/{venta_id}/factura/pdf", tags=["Facturación"])
def descargar_factura_pdf(
    venta_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(*_ROLES_POS)),
):
    """
    Genera y descarga la factura de una venta ya cobrada en formato PDF,
    con el nombre del negocio, los productos, la discriminación del
    impuesto (agrupada por tipo), el vendedor, el método de pago, el cambio
    y los datos del proveedor del sistema (SoftLegacy).
    """
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    datos = construir_datos_factura(venta)
    archivo = generar_pdf_factura(datos)

    nombre_archivo = f"factura_{venta.id}.pdf"
    return StreamingResponse(
        archivo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
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
    Envía la factura de una venta ya cobrada al correo indicado, con el PDF
    adjunto (incluyendo la discriminación del impuesto agrupada por tipo).
    Limitado a 5 envíos por minuto por IP para evitar que se use el servidor
    de correo para enviar spam. Queda registrado en logs/negocio.log quién
    envió la factura, a qué venta corresponde y a qué correo se envió, para
    trazabilidad.
    """
    venta = _obtener_venta_facturable_o_error(venta_id, db)
    datos = construir_datos_factura(venta)
    archivo_pdf = generar_pdf_factura(datos)

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