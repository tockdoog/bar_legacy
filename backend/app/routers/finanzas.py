# Ruta: backend/app/routers/finanzas.py
# Endpoints del modulo "Analisis Financiero e Impuestos": configuracion de
# impuestos y margen deseado, calculo de precio de venta recomendado,
# analisis de rentabilidad por producto (recomendaciones y advertencias,
# respetando la configuracion propia de cada producto si la tiene) y
# resumen financiero por periodo (ingresos, gastos, ganancia e impuestos
# estimados).
#
# PERMISOS: todo el modulo requiere el permiso granular "finanzas_gestionar"
# (el administrador siempre lo tiene por su rol; un empleado solo si el
# administrador se lo asigno desde Usuarios). Se usa un permiso propio, no
# compartido con "reportes_ver", porque aqui ademas de CONSULTAR informacion
# financiera sensible tambien se puede MODIFICAR la configuracion global de
# impuesto y margen del negocio (ver actualizar_configuracion_financiera).

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.models.producto import Producto
from app.models.venta import Venta, EstadoVenta
from app.models.compra import Compra
from app.models.finanzas import (
    ConfiguracionFinanciera,
    TipoImpuesto,
    ETIQUETAS_TIPO_IMPUESTO,
    PORCENTAJES_REFERENCIA,
)
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
from app.logs.logger import registrar_negocio

router = APIRouter(prefix="/api/finanzas", tags=["Analisis Financiero"])


def _obtener_configuracion(db: Session) -> ConfiguracionFinanciera:
    """
    Devuelve la unica fila de configuracion financiera (id=1), creandola con
    valores por defecto si el sistema nunca la ha configurado (primer uso).
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


def _a_respuesta_configuracion(configuracion: ConfiguracionFinanciera) -> ConfiguracionFinancieraRespuesta:
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
    fin = fecha_fin or date.today()
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
def obtener_configuracion_financiera(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """Devuelve la configuracion actual (global) de impuestos y margen de utilidad deseado."""
    configuracion = _obtener_configuracion(db)
    return _a_respuesta_configuracion(configuracion)


@router.get("/impuestos-disponibles", summary="Listar los tipos de impuesto disponibles")
def listar_tipos_impuesto(
    usuario=Depends(requerir_permiso("finanzas_gestionar")),
):
    """
    Devuelve la lista de tipos de impuesto que se pueden elegir (sin
    impuesto, IVA, INC, personalizado), junto con un porcentaje de
    referencia editable. Se usa tanto en la configuracion global como en la
    configuracion propia de un producto individual (Inventario).
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
    """Actualiza el tipo de impuesto global, su porcentaje, el margen deseado y el margen mínimo saludable."""
    configuracion = _obtener_configuracion(db)

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
    Calcula el precio de venta recomendado a partir de un costo (de un
    producto existente o de un valor libre). Si el producto tiene su PROPIA
    configuración de impuesto/margen activada, se usa esa; si no, se usa la
    configuración global (o la enviada puntualmente en la petición, que
    siempre tiene la prioridad más alta si se indica un margen).
    """
    configuracion_global = _obtener_configuracion(db)

    if datos.producto_id is not None:
        producto = db.query(Producto).filter(Producto.id == datos.producto_id).first()
        if producto is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
        costo_compra = producto.precio_compra
        config_efectiva = resolver_configuracion_efectiva(producto, configuracion_global)
        porcentaje_impuesto = config_efectiva.porcentaje_impuesto
        margen_por_defecto = config_efectiva.margen_utilidad_deseado
    else:
        costo_compra = datos.costo_compra
        porcentaje_impuesto = configuracion_global.porcentaje_impuesto
        margen_por_defecto = configuracion_global.margen_utilidad_deseado

    margen = datos.margen_utilidad_deseado or margen_por_defecto

    resultado = calcular_precio_recomendado(
        costo_compra=costo_compra,
        margen_utilidad_deseado=margen,
        porcentaje_impuesto=porcentaje_impuesto,
        incluir_impuesto=datos.incluir_impuesto,
    )

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
    """
    Analiza cada producto activo del inventario usando SU PROPIA
    configuración de impuesto/margen si la tiene activada, o la
    configuración global en caso contrario.
    """
    configuracion_global = _obtener_configuracion(db)
    productos = db.query(Producto).filter(Producto.activo == True).all()  # noqa: E712

    resultados: list[ProductoAnalisisFinanciero] = []
    for producto in productos:
        config_efectiva = resolver_configuracion_efectiva(producto, configuracion_global)

        estado, mensaje = evaluar_estado_producto(
            producto.precio_compra,
            producto.precio_venta,
            configuracion_global.margen_minimo_saludable,
        )
        margen_actual = calcular_margen_actual(producto.precio_compra, producto.precio_venta)

        precio_recomendado = calcular_precio_recomendado(
            costo_compra=producto.precio_compra,
            margen_utilidad_deseado=config_efectiva.margen_utilidad_deseado,
            porcentaje_impuesto=config_efectiva.porcentaje_impuesto,
            incluir_impuesto=True,
        ).precio_venta_final

        # Si el producto tiene configuración propia, se aclara en el mensaje
        # para que el administrador entienda por qué difiere de la global.
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
    Calcula el panorama financiero del negocio en un periodo: cuanto entro
    por ventas, cuanto costaron esos productos, cuanto se gasto en compras a
    proveedores, la ganancia bruta y neta (descontando el impuesto estimado
    sobre las ventas, sumando el impuesto ya congelado línea por línea), y
    cuantos productos estan en perdida o bajo margen segun la configuracion
    (propia o global) de cada uno.
    """
    inicio, fin = _resolver_rango_fechas(fecha_inicio, fecha_fin)
    configuracion_global = _obtener_configuracion(db)

    ventas_pagadas = (
        db.query(Venta)
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
            # Suma el impuesto ya congelado en cada línea (si la venta es
            # anterior a este campo, queda en 0 y no afecta el total).
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

    productos = db.query(Producto).filter(Producto.activo == True).all()  # noqa: E712
    productos_en_perdida = 0
    productos_bajo_margen = 0
    for producto in productos:
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