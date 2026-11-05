# Ruta: backend/app/utils/generador_factura.py
# Construye los datos estructurados de la factura de una venta ya cobrada
# (usados para imprimir una tirilla desde el navegador) y genera el archivo
# PDF correspondiente con un diseño profesional de factura, en pesos
# colombianos, incluyendo la DISCRIMINACIÓN DEL IMPUESTO agrupada por tipo.
# El impuesto de cada línea ya viene CONGELADO desde el momento en que el
# producto se agregó al carrito (ver DetalleVenta.tipo/porcentaje/etiqueta
# _impuesto_aplicado en routers/ventas.py), por lo que esta factura nunca
# cambia aunque más adelante se edite el impuesto del producto o la
# configuración global: no necesita consultar la base de datos. No depende
# de ningún nicho de negocio: solo usa los datos genéricos de la venta.

from collections import OrderedDict
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)

from app.config import configuracion
from app.models.venta import Venta, ETIQUETAS_METODO_PAGO

PROVEEDOR_NOMBRE = "SoftLegacy"
PROVEEDOR_SITIO_WEB = "https://softlegacy.vercel.app"

COLOR_DORADO = colors.HexColor("#C9A24B")
COLOR_NEGRO = colors.HexColor("#1C1C1C")

ETIQUETA_SIN_IMPUESTO = "Sin impuesto"


def _formatear_cop(valor: float | None) -> str:
    """Formatea un número como pesos colombianos con punto como separador de miles."""
    if valor is None:
        valor = 0
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def _calcular_discriminacion_impuesto(venta: Venta) -> list[dict]:
    """
    Agrupa las líneas de la venta por el impuesto que tenían CONGELADO al
    momento de agregarse al carrito (etiqueta + porcentaje), y calcula la
    base gravable y el valor del impuesto de cada grupo:

        base_gravable = subtotal_grupo / (1 + porcentaje/100)
        valor_impuesto = subtotal_grupo - base_gravable

    Devuelve una lista de grupos (uno por combinación etiqueta+porcentaje
    distinta), en el orden en que aparecieron. Líneas de ventas creadas
    ANTES de este campo (porcentaje_impuesto_aplicado es None) se agrupan
    como "Sin impuesto" para no inventar un impuesto que no se congeló en
    su momento.
    """
    grupos: "OrderedDict[tuple[str, float], dict]" = OrderedDict()

    for detalle in venta.detalles:
        porcentaje = detalle.porcentaje_impuesto_aplicado or 0.0
        etiqueta = detalle.etiqueta_impuesto_aplicado or ETIQUETA_SIN_IMPUESTO
        clave = (etiqueta, porcentaje)

        if clave not in grupos:
            grupos[clave] = {"etiqueta": etiqueta, "porcentaje": porcentaje, "subtotal": 0.0}
        grupos[clave]["subtotal"] += detalle.subtotal

    resultado = []
    for grupo in grupos.values():
        subtotal = round(grupo["subtotal"], 2)
        porcentaje = grupo["porcentaje"]

        if porcentaje > 0:
            base_gravable = round(subtotal / (1 + porcentaje / 100), 2)
            valor_impuesto = round(subtotal - base_gravable, 2)
        else:
            base_gravable = subtotal
            valor_impuesto = 0.0

        resultado.append(
            {
                "etiqueta": grupo["etiqueta"],
                "porcentaje": porcentaje,
                "base_gravable": base_gravable,
                "valor_impuesto": valor_impuesto,
                "aplica": porcentaje > 0,
            }
        )

    return resultado


def construir_datos_factura(venta: Venta) -> dict:
    """
    Construye un diccionario con toda la información necesaria para mostrar
    o imprimir la factura de una venta ya cobrada: datos del negocio, de la
    transacción, los productos, los totales, la discriminación del impuesto
    (agrupada por tipo, ya que distintos productos pueden tener impuestos
    distintos), el método de pago y los datos del proveedor del sistema.
    """
    items = [
        {
            "nombre": detalle.producto.nombre if detalle.producto else "Producto eliminado",
            "cantidad": detalle.cantidad,
            "precio_unitario": detalle.precio_venta_unitario,
            "subtotal": detalle.subtotal,
        }
        for detalle in venta.detalles
    ]

    metodo_pago_texto = (
        ETIQUETAS_METODO_PAGO.get(venta.metodo_pago, "—") if venta.metodo_pago else "—"
    )

    grupos_impuesto = _calcular_discriminacion_impuesto(venta)

    return {
        "negocio": {
            "nombre": configuracion.NOMBRE_NEGOCIO,
            "nit": configuracion.NIT_NEGOCIO,
            "direccion": configuracion.DIRECCION_NEGOCIO,
            "telefono": configuracion.TELEFONO_NEGOCIO,
        },
        "venta": {
            "id": venta.id,
            "fecha": (venta.fecha_pago or datetime.utcnow()).isoformat(),
            "mesa": str(venta.mesa.numero) if venta.mesa_id and venta.mesa else None,
            "vendedor": venta.usuario.nombre_completo if venta.usuario else "—",
            "estado": venta.estado.value,
        },
        "items": items,
        "totales": {
            "subtotal": venta.subtotal,
            "total": venta.total,
            "monto_pagado": venta.monto_pagado,
            "cambio": venta.cambio,
            "metodo_pago": metodo_pago_texto,
        },
        "grupos_impuesto": grupos_impuesto,
        "proveedor": {
            "nombre": PROVEEDOR_NOMBRE,
            "sitio_web": PROVEEDOR_SITIO_WEB,
        },
    }


def generar_pdf_factura(datos: dict) -> BytesIO:
    """
    Genera el archivo PDF de la factura a partir del diccionario devuelto
    por construir_datos_factura(), con un diseño profesional: encabezado con
    los datos del negocio, detalle de productos, discriminación del
    impuesto (una fila por cada tipo de impuesto distinto involucrado en la
    venta), totales, método de pago y pie de página con los datos del
    proveedor del sistema (SoftLegacy).
    """
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = []

    estilo_titulo_negocio = ParagraphStyle(
        "TituloNegocio", parent=estilos["Title"], alignment=TA_CENTER, textColor=COLOR_NEGRO,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloNegocio", parent=estilos["Normal"], alignment=TA_CENTER,
        fontSize=9, textColor=colors.grey,
    )
    estilo_pie = ParagraphStyle(
        "Pie", parent=estilos["Normal"], alignment=TA_CENTER, fontSize=8, textColor=colors.grey,
    )

    negocio = datos["negocio"]
    venta = datos["venta"]
    totales = datos["totales"]
    grupos_impuesto = datos["grupos_impuesto"]
    proveedor = datos["proveedor"]

    elementos.append(Paragraph(negocio["nombre"], estilo_titulo_negocio))
    datos_contacto = " · ".join(
        texto for texto in [negocio.get("nit"), negocio.get("direccion"), negocio.get("telefono")] if texto
    )
    if datos_contacto:
        elementos.append(Paragraph(datos_contacto, estilo_subtitulo))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(HRFlowable(width="100%", color=COLOR_DORADO, thickness=1.2))
    elementos.append(Spacer(1, 0.4 * cm))

    fecha_legible = datetime.fromisoformat(venta["fecha"]).strftime("%d/%m/%Y %H:%M")
    elementos.append(Paragraph(f"<b>Factura de venta #{venta['id']}</b>", estilos["Heading2"]))
    elementos.append(Paragraph(f"Fecha y hora: {fecha_legible}", estilos["Normal"]))
    if venta.get("mesa"):
        elementos.append(Paragraph(f"Mesa: {venta['mesa']}", estilos["Normal"]))
    elementos.append(Paragraph(f"Atendido por: {venta['vendedor']}", estilos["Normal"]))
    if venta.get("estado") == "anulada":
        elementos.append(Paragraph("<b>Esta venta fue ANULADA posteriormente.</b>", estilos["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    filas = [["Producto", "Cant.", "Precio unit.", "Subtotal"]]
    for item in datos["items"]:
        filas.append([
            item["nombre"],
            str(item["cantidad"]),
            _formatear_cop(item["precio_unitario"]),
            _formatear_cop(item["subtotal"]),
        ])

    tabla = Table(filas, colWidths=[8 * cm, 2 * cm, 3.2 * cm, 3.2 * cm], repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_NEGRO),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F4EC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_DORADO),
            ]
        )
    )
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.5 * cm))

    # --- Bloque: discriminación del impuesto, una fila por cada tipo de
    # impuesto distinto involucrado en la venta (ej: unos productos con IVA,
    # otros exentos). Solo se muestran los grupos que sí tienen impuesto. ---
    filas_impuesto = []
    for grupo in grupos_impuesto:
        if grupo["aplica"]:
            filas_impuesto.append(["Base gravable", _formatear_cop(grupo["base_gravable"])])
            filas_impuesto.append(
                [f"{grupo['etiqueta']} ({grupo['porcentaje']}%)", _formatear_cop(grupo["valor_impuesto"])]
            )

    if filas_impuesto:
        tabla_impuesto = Table(filas_impuesto, colWidths=[10 * cm, 6.4 * cm])
        tabla_impuesto.setStyle(
            TableStyle(
                [
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        elementos.append(tabla_impuesto)
        elementos.append(Spacer(1, 0.3 * cm))

    filas_totales = [
        ["Subtotal", _formatear_cop(totales["subtotal"])],
        ["TOTAL", _formatear_cop(totales["total"])],
        ["Método de pago", totales["metodo_pago"]],
        ["Pagó con", _formatear_cop(totales["monto_pagado"])],
        ["Cambio entregado", _formatear_cop(totales["cambio"])],
    ]
    tabla_totales = Table(filas_totales, colWidths=[10 * cm, 6.4 * cm])
    tabla_totales.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("LINEABOVE", (0, 1), (-1, 1), 0.8, COLOR_DORADO),
                ("LINEBELOW", (0, 1), (-1, 1), 0.8, COLOR_DORADO),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elementos.append(tabla_totales)
    elementos.append(Spacer(1, 1 * cm))

    elementos.append(HRFlowable(width="100%", color=colors.lightgrey, thickness=0.7))
    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(Paragraph("¡Gracias por su compra!", estilo_pie))
    elementos.append(
        Paragraph(f"Sistema desarrollado por {proveedor['nombre']} · {proveedor['sitio_web']}", estilo_pie)
    )

    documento.build(elementos)
    buffer.seek(0)
    return buffer