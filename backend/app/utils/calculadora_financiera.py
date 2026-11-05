# Ruta: backend/app/utils/calculadora_financiera.py
# Motor de calculo financiero puro (sin dependencias de base de datos salvo
# los tipos ConfiguracionFinanciera y Producto): calcula el precio de venta
# recomendado segun costo, margen de utilidad deseado e impuesto configurado,
# evalua el estado de rentabilidad de productos ya existentes, y resuelve
# cual configuracion de impuesto/margen aplica a un producto puntual (la
# global del negocio, o la propia del producto si la tiene activada). No
# depende de ningun rubro de negocio especifico.

from dataclasses import dataclass

from app.models.finanzas import ConfiguracionFinanciera, TipoImpuesto, ETIQUETAS_TIPO_IMPUESTO


@dataclass
class ResultadoCalculoPrecio:
    """Estructura interna con el desglose completo de un calculo de precio."""
    costo_compra: float
    margen_utilidad_aplicado: float
    utilidad_por_unidad: float
    precio_venta_sin_impuesto: float
    porcentaje_impuesto_aplicado: float
    valor_impuesto: float
    precio_venta_final: float
    margen_sobre_costo: float


@dataclass
class ConfiguracionEfectivaProducto:
    """
    Configuración de impuesto y margen que realmente aplica a un producto,
    ya resuelta: o la global del negocio, o la propia del producto si la
    tiene activada. Se usa tanto para la calculadora/recomendaciones como
    para congelar el impuesto en cada línea de venta al momento de cobrar.
    """
    tipo_impuesto: TipoImpuesto
    porcentaje_impuesto: float
    etiqueta_impuesto: str
    margen_utilidad_deseado: float
    es_configuracion_propia: bool


def resolver_configuracion_efectiva(producto, configuracion_global: ConfiguracionFinanciera) -> ConfiguracionEfectivaProducto:
    """
    Determina qué impuesto y margen aplican realmente a un producto: si
    "usar_configuracion_global" es True (o el producto no trae ese campo,
    por compatibilidad con datos antiguos), se usa la configuración global
    del negocio; si es False, se usa la configuración propia guardada en el
    producto.
    """
    usa_global = getattr(producto, "usar_configuracion_global", True)

    if usa_global:
        etiqueta = (
            configuracion_global.nombre_impuesto_personalizado
            if configuracion_global.tipo_impuesto == TipoImpuesto.PERSONALIZADO
            and configuracion_global.nombre_impuesto_personalizado
            else ETIQUETAS_TIPO_IMPUESTO[configuracion_global.tipo_impuesto]
        )
        return ConfiguracionEfectivaProducto(
            tipo_impuesto=configuracion_global.tipo_impuesto,
            porcentaje_impuesto=configuracion_global.porcentaje_impuesto,
            etiqueta_impuesto=etiqueta,
            margen_utilidad_deseado=configuracion_global.margen_utilidad_deseado,
            es_configuracion_propia=False,
        )

    tipo_propio = producto.tipo_impuesto_propio or TipoImpuesto.SIN_IMPUESTO
    porcentaje_propio = producto.porcentaje_impuesto_propio or 0.0
    etiqueta_propia = (
        producto.nombre_impuesto_propio_personalizado
        if tipo_propio == TipoImpuesto.PERSONALIZADO and producto.nombre_impuesto_propio_personalizado
        else ETIQUETAS_TIPO_IMPUESTO[tipo_propio]
    )
    margen_propio = producto.margen_utilidad_propio or configuracion_global.margen_utilidad_deseado

    return ConfiguracionEfectivaProducto(
        tipo_impuesto=tipo_propio,
        porcentaje_impuesto=porcentaje_propio,
        etiqueta_impuesto=etiqueta_propia,
        margen_utilidad_deseado=margen_propio,
        es_configuracion_propia=True,
    )


def calcular_precio_recomendado(
    costo_compra: float,
    margen_utilidad_deseado: float,
    porcentaje_impuesto: float,
    incluir_impuesto: bool = True,
) -> ResultadoCalculoPrecio:
    """
    Calcula el precio de venta recomendado a partir de un costo.

    El margen de utilidad deseado se interpreta como porcentaje SOBRE EL
    PRECIO DE VENTA (formula estandar de margen bruto: margen = (precio_venta
    - costo) / precio_venta), no como un recargo sobre el costo (markup).
    Esto evita el error comun de confundir "margen" con "markup": un margen
    del 30% NO equivale a sumarle 30% al costo.

    Ejemplo: costo = 10.000 COP, margen deseado = 30%
        precio_venta_sin_impuesto = 10.000 / (1 - 0.30) = 14.286 COP
        utilidad_por_unidad = 4.286 COP (el 30% exacto de 14.286)
    """
    fraccion_margen = margen_utilidad_deseado / 100
    precio_venta_sin_impuesto = round(costo_compra / (1 - fraccion_margen), 2)
    utilidad_por_unidad = round(precio_venta_sin_impuesto - costo_compra, 2)

    valor_impuesto = 0.0
    precio_venta_final = precio_venta_sin_impuesto
    if incluir_impuesto and porcentaje_impuesto > 0:
        valor_impuesto = round(precio_venta_sin_impuesto * (porcentaje_impuesto / 100), 2)
        precio_venta_final = round(precio_venta_sin_impuesto + valor_impuesto, 2)

    margen_sobre_costo = (
        round((utilidad_por_unidad / costo_compra) * 100, 2) if costo_compra > 0 else 0.0
    )

    return ResultadoCalculoPrecio(
        costo_compra=round(costo_compra, 2),
        margen_utilidad_aplicado=margen_utilidad_deseado,
        utilidad_por_unidad=utilidad_por_unidad,
        precio_venta_sin_impuesto=precio_venta_sin_impuesto,
        porcentaje_impuesto_aplicado=porcentaje_impuesto if incluir_impuesto else 0.0,
        valor_impuesto=valor_impuesto,
        precio_venta_final=precio_venta_final,
        margen_sobre_costo=margen_sobre_costo,
    )


def calcular_margen_actual(precio_compra: float, precio_venta: float) -> float:
    """
    Calcula el margen de utilidad actual de un producto ya existente, con la
    misma formula (margen sobre precio de venta). Si el precio de venta es
    0 o negativo, se devuelve -100 para representar una perdida total sin
    dividir por cero.
    """
    if precio_venta <= 0:
        return -100.0
    return round(((precio_venta - precio_compra) / precio_venta) * 100, 2)


def evaluar_estado_producto(
    precio_compra: float,
    precio_venta: float,
    margen_minimo_saludable: float,
) -> tuple[str, str]:
    """
    Evalua el estado de rentabilidad de un producto y devuelve una tupla
    (estado, mensaje) lista para mostrar como advertencia al administrador.
    Estados posibles: "perdida", "bajo_margen", "saludable".
    """
    if precio_venta < precio_compra:
        diferencia = round(precio_compra - precio_venta, 2)
        return (
            "perdida",
            f"Se está vendiendo por debajo del costo: se pierden {diferencia} "
            f"COP por cada unidad vendida.",
        )

    margen_actual = calcular_margen_actual(precio_compra, precio_venta)
    if margen_actual < margen_minimo_saludable:
        return (
            "bajo_margen",
            f"El margen actual es de {margen_actual}%, por debajo del mínimo "
            f"saludable configurado ({margen_minimo_saludable}%).",
        )

    return ("saludable", f"Margen actual saludable: {margen_actual}%.")