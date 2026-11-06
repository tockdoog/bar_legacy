# Ruta: backend/app/routers/finanzas.py
# Endpoints del módulo "Análisis Financiero e Impuestos": configuración de impuestos
# y margen, cálculo de precio de venta recomendado, análisis de rentabilidad por
# producto y resumen financiero por periodo (ingresos, gastos, ganancia e impuestos
# estimados). Montos en pesos colombianos (COP).
#
# PERMISOS: todo el módulo requiere el permiso "finanzas_gestionar" (el administrador
# siempre lo tiene). Es un permiso propio porque aquí también se MODIFICA la
# configuración global de impuesto y margen del negocio.
#
# CAMBIOS: el resumen carga los productos de cada venta en una sola consulta (antes una
# por venta, lento con Neon); las fechas usan hoy_colombia(); un margen de 0 % ya no se
# reemplaza por el margen por defecto; un margen de 100 % o más responde 400 en vez de 500.

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.logs.logger import registrar_negocio
from app.models.compra import Compra
from app.models.finanzas import (
    ConfiguracionFinanciera,
    TipoImpuesto,
    ETIQUETAS_TIPO_IMPUESTO,
    PORCENTAJES_REFERENCIA,
)
from app.models.producto import Producto
from app.models.venta import Venta, EstadoVenta
from app.schemas.finanzas import (
    ConfiguracionFinancieraActualizar,
    ConfiguracionFinancieraRespuesta,
    CalculoPrecioSolicitud,
    CalculoPrecioRespuesta,
    ProductoAnalisisFinanciero,
    ResumenFinancieroRespuesta,
)
from app.utils.calculadora_financiera import (
    calcular_precio_recomendado,
    calcular_margen_actual,
    evaluar_estado_producto,
    resolver_configuracion_efectiva,
)
from app.utils.configuracion_financiera import obtener_configuracion_financiera
from app.utils.zona_horaria import hoy_colombia

router = APIRouter(prefix="/api/finanzas", tags=["Analisis Financiero"])


def _a_respuesta_configuracion(configuracion: ConfiguracionFinanciera) -> ConfiguracionFinancieraRespuesta:
    """Convierte la configuración guardada en su respuesta, con la etiqueta legible del impuesto."""
    etiqueta = (
        configuracion.nombre_impuesto_personalizado
        if configuracion.tipo_impuesto == TipoImpuesto.PERSONALIZADO and configuracion.nombre_impuesto_personalizado
        else ETIQUETAS_TIPO_IMPUESTO[configuracion.tipo_impuesto]
    )
    return ConfiguracionFinancieraRespuesta(
        tipo_impuesto=configuracion.tipo_impuesto,
        etiqueta_impuesto=etiqueta,
        porcentaje_impuesto=configuracion.porcentaje_impuesto,
        nombre_impuesto_personalizado=configuracion.nombre_impuesto_personalizado,
        margen_utilidad_deseado=configuracion.margen_utilidad_deseado,
        margen_minimo_saludable=configuracion.margen_minimo_saludable,
        fecha_actualizacion=configuracion.fecha_actualizacion,
    )


def _resolver_rango_fechas(fecha_inicio: date | None, fecha_fin: date | None) -> tuple[datetime, datetime]:
    """Convierte las fechas recibidas en un rango completo (por defecto, los últimos 30 días de Colombia)."""
    fin = fecha_fin or hoy_colombia()
    inicio = fecha_inicio or (fin - timedelta(days=30))
    if inicio > fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser posterior a la fecha final.",
        )
    return datetime.combine(inicio, time.min), datetime.combine(fin, time.max)


@router.get(
    "/configuracion",
    response_model=ConfiguracionFinancieraRespuesta,
    summary="Consultar configuracion de impuestos y margen",
)
def obtener_configuracion(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """Devuelve la configuración global actual de impuestos y margen de utilidad deseado."""
    return _a_respuesta_configuracion(obtener_configuracion_financiera(db))


@router.get("/impuestos-disponibles", summary="Listar los tipos de impuesto disponibles")
def listar_tipos_impuesto(
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """
    Lista los tipos de impuesto elegibles (sin impuesto, IVA, INC, personalizado) con un
    porcentaje de referencia editable. Se usa en la configuración global y en la de cada producto.
    """
    return [
        {
            "tipo": tipo.value,
            "etiqueta": ETIQUETAS_TIPO_IMPUESTO[tipo],
            "porcentaje_referencia": PORCENTAJES_REFERENCIA[tipo],
        }
        for tipo in TipoImpuesto
    ]


@router.put(
    "/configuracion",
    response_model=ConfiguracionFinancieraRespuesta,
    summary="Actualizar configuracion de impuestos y margen",
)
def actualizar_configuracion_financiera(
    datos: ConfiguracionFinancieraActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """Actualiza el impuesto global, su porcentaje, el margen deseado y el margen mínimo saludable."""
    configuracion = obtener_configuracion_financiera(db)

    configuracion.tipo_impuesto = datos.tipo_impuesto
    configuracion.porcentaje_impuesto = datos.porcentaje_impuesto
    configuracion.nombre_impuesto_personalizado = (
        datos.nombre_impuesto_personalizado if datos.tipo_impuesto == TipoImpuesto.PERSONALIZADO else None
    )
    configuracion.margen_utilidad_deseado = datos.margen_utilidad_deseado
    configuracion.margen_minimo_saludable = datos.margen_minimo_saludable

    db.commit()
    db.refresh(configuracion)

    registrar_negocio(
        f"Actualizó la configuración financiera global "
        f"(impuesto: {datos.tipo_impuesto.value} {datos.porcentaje_impuesto}%; "
        f"margen deseado: {datos.margen_utilidad_deseado}%)",
        usuario=usuario.nombre_usuario,
    )
    return _a_respuesta_configuracion(configuracion)


@router.post(
    "/calcular-precio",
    response_model=CalculoPrecioRespuesta,
    summary="Calcular precio de venta recomendado",
)
def calcular_precio(
    datos: CalculoPrecioSolicitud,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """
    Calcula el precio de venta recomendado a partir de un costo (de un producto o libre).
    Si el producto tiene configuración propia se usa esa; si no, la global. El margen
    enviado en la petición (incluido 0) tiene siempre la prioridad más alta.
    """
    configuracion_global = obtener_configuracion_financiera(db)

    if datos.producto_id is not None:
        producto = db.query(Producto).filter(Producto.id == datos.producto_id).first()
        if producto is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
        costo_compra = producto.precio_compra
        config_efectiva = resolver_configuracion_efectiva(producto, configuracion_global)
        porcentaje_impuesto = config_efectiva.porcentaje_impuesto
        margen_por_defecto = config_efectiva.margen_utilidad_deseado
    else:
        if datos.costo_compra is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Indica un producto o un costo de compra para calcular el precio.",
            )
        costo_compra = datos.costo_compra
        porcentaje_impuesto = configuracion_global.porcentaje_impuesto
        margen_por_defecto = configuracion_global.margen_utilidad_deseado

    margen = datos.margen_utilidad_deseado if datos.margen_utilidad_deseado is not None else margen_por_defecto

    try:
        resultado = calcular_precio_recomendado(
            costo_compra=costo_compra,
            margen_utilidad_deseado=margen,
            porcentaje_impuesto=porcentaje_impuesto,
            incluir_impuesto=datos.incluir_impuesto,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    return CalculoPrecioRespuesta(
        costo_compra=resultado.costo_compra,
        margen_utilidad_aplicado=resultado.margen_utilidad_aplicado,
        utilidad_por_unidad=resultado.utilidad_por_unidad,
        precio_venta_sin_impuesto=resultado.precio_venta_sin_impuesto,
        porcentaje_impuesto_aplicado=resultado.porcentaje_impuesto_aplicado,
        valor_impuesto=resultado.valor_impuesto,
        precio_venta_final=resultado.precio_venta_final,
        margen_sobre_costo=resultado.margen_sobre_costo,
    )


@router.get(
    "/productos/analisis",
    response_model=list[ProductoAnalisisFinanciero],
    summary="Analisis de rentabilidad por producto",
)
def analizar_productos(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """Analiza cada producto activo con su configuración propia (si la tiene) o con la global."""
    configuracion_global = obtener_configuracion_financiera(db)
    productos = db.query(Producto).filter(Producto.activo.is_(True)).all()

    resultados: list[ProductoAnalisisFinanciero] = []
    for producto in productos:
        config_efectiva = resolver_configuracion_efectiva(producto, configuracion_global)

        estado, mensaje = evaluar_estado_producto(
            producto.precio_compra,
            producto.precio_venta,
            configuracion_global.margen_minimo_saludable,
        )
        margen_actual = calcular_margen_actual(producto.precio_compra, producto.precio_venta)

        try:
            precio_recomendado = calcular_precio_recomendado(
                costo_compra=producto.precio_compra,
                margen_utilidad_deseado=config_efectiva.margen_utilidad_deseado,
                porcentaje_impuesto=config_efectiva.porcentaje_impuesto,
                incluir_impuesto=True,
            ).precio_venta_final
        except ValueError:
            precio_recomendado = producto.precio_venta  # Margen inválido guardado: no se recomienda un cambio

        # Si el producto tiene configuración propia, se aclara por qué difiere de la global
        if config_efectiva.es_configuracion_propia:
            mensaje = f"{mensaje} (impuesto propio: {config_efectiva.etiqueta_impuesto} {config_efectiva.porcentaje_impuesto}%)"

        resultados.append(
            ProductoAnalisisFinanciero(
                producto_id=producto.id,
                nombre=producto.nombre,
                precio_compra=producto.precio_compra,
                precio_venta_actual=producto.precio_venta,
                utilidad_actual_unitaria=round(producto.precio_venta - producto.precio_compra, 2),
                margen_actual_porcentaje=margen_actual,
                precio_venta_recomendado=precio_recomendado,
                estado=estado,
                mensaje=mensaje,
            )
        )

    orden_estado = {"perdida": 0, "bajo_margen": 1, "saludable": 2}
    resultados.sort(key=lambda item: orden_estado.get(item.estado, 99))
    return resultados


@router.get(
    "/resumen",
    response_model=ResumenFinancieroRespuesta,
    summary="Resumen financiero del periodo",
)
def resumen_financiero(
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """
    Panorama financiero de un periodo: ingresos por ventas, costo de lo vendido, gasto en
    compras, ganancia bruta y neta (descontando el impuesto ya congelado en cada línea de
    venta) y cuántos productos están en pérdida o bajo margen.
    """
    inicio, fin = _resolver_rango_fechas(fecha_inicio, fecha_fin)
    configuracion_global = obtener_configuracion_financiera(db)

    # Los detalles se cargan junto con las ventas (una sola consulta, no una por venta)
    ventas_pagadas = (
        db.query(Venta)
        .options(joinedload(Venta.detalles))
        .filter(
            Venta.estado == EstadoVenta.PAGADA,
            Venta.fecha_pago >= inicio,
            Venta.fecha_pago <= fin,
        )
        .all()
    )

    total_ingresos_ventas = round(sum(venta.total for venta in ventas_pagadas), 2)

    total_costo_ventas = 0.0
    valor_impuesto_estimado = 0.0
    for venta in ventas_pagadas:
        for detalle in venta.detalles:
            total_costo_ventas += detalle.cantidad * detalle.precio_compra_unitario
            # Impuesto ya congelado en la línea (0 en ventas anteriores a este campo)
            porcentaje_linea = detalle.porcentaje_impuesto_aplicado or 0.0
            if porcentaje_linea > 0:
                subtotal_linea = detalle.subtotal
                base_linea = subtotal_linea / (1 + porcentaje_linea / 100)
                valor_impuesto_estimado += subtotal_linea - base_linea

    total_costo_ventas = round(total_costo_ventas, 2)
    valor_impuesto_estimado = round(valor_impuesto_estimado, 2)

    total_gastos_compras = round(
        db.query(func.coalesce(func.sum(Compra.total), 0.0))
        .filter(Compra.fecha >= inicio, Compra.fecha <= fin)
        .scalar(),
        2,
    )

    ganancia_bruta = round(total_ingresos_ventas - total_costo_ventas, 2)
    ganancia_neta_estimada = round(ganancia_bruta - valor_impuesto_estimado, 2)
    margen_promedio_real = (
        round((ganancia_bruta / total_ingresos_ventas) * 100, 2) if total_ingresos_ventas > 0 else 0.0
    )

    productos_en_perdida = 0
    productos_bajo_margen = 0
    for producto in db.query(Producto).filter(Producto.activo.is_(True)).all():
        estado, _ = evaluar_estado_producto(
            producto.precio_compra, producto.precio_venta, configuracion_global.margen_minimo_saludable
        )
        if estado == "perdida":
            productos_en_perdida += 1
        elif estado == "bajo_margen":
            productos_bajo_margen += 1

    return ResumenFinancieroRespuesta(
        fecha_inicio=inicio,
        fecha_fin=fin,
        total_ingresos_ventas=total_ingresos_ventas,
        total_costo_ventas=total_costo_ventas,
        total_gastos_compras=total_gastos_compras,
        ganancia_bruta=ganancia_bruta,
        valor_impuesto_estimado_ventas=valor_impuesto_estimado,
        ganancia_neta_estimada=ganancia_neta_estimada,
        margen_promedio_real=margen_promedio_real,
        cantidad_ventas=len(ventas_pagadas),
        productos_en_perdida=productos_en_perdida,
        productos_bajo_margen=productos_bajo_margen,
    )