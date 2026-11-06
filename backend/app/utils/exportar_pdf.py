# Ruta: backend/app/utils/exportar_pdf.py
# Convierte el resultado de un reporte (DataFrame + resumen) en un archivo PDF listo
# para descargar, con montos en pesos colombianos (ReportLab).
#
# CAMBIOS: los textos largos (productos anulados, desglose de pago mixto) se ajustan en
# varias líneas dentro de su celda en vez de salirse de la hoja; los anchos de columna se
# reparten según el contenido; con más de 6 columnas la hoja pasa a horizontal; las
# columnas de dinero se alinean a la derecha. Todo texto se escapa antes de entrar a ReportLab.

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.utils.formato_reportes import es_resumen_monetario, formatear_cop
from app.utils.generador_reportes import ResultadoReporte
from app.utils.zona_horaria import ahora_colombia

# Colores de la identidad visual del sistema
COLOR_DORADO = colors.HexColor("#C9A24B")
COLOR_NEGRO = colors.HexColor("#1C1C1C")

# Con más columnas que este límite, la hoja se imprime en horizontal
MAXIMO_COLUMNAS_VERTICAL = 6
MARGEN_CM = 1.5


def _anchos_de_columna(columnas: list[str], filas: list[list[str]], ancho_total: float) -> list[float]:
    """Reparte el ancho disponible entre las columnas según el largo de su contenido (entre 6 y 40 caracteres)."""
    pesos = []
    for indice, nombre in enumerate(columnas):
        largo_maximo = max([len(nombre)] + [len(fila[indice]) for fila in filas])
        pesos.append(min(max(largo_maximo, 6), 40))
    suma = sum(pesos)
    return [ancho_total * peso / suma for peso in pesos]


def generar_pdf(resultado: ResultadoReporte) -> BytesIO:
    """Construye un archivo PDF en memoria a partir de un ResultadoReporte."""
    columnas = list(resultado.dataframe.columns)
    pagina = landscape(letter) if len(columnas) > MAXIMO_COLUMNAS_VERTICAL else letter

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=MARGEN_CM * cm,
        rightMargin=MARGEN_CM * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = []

    # --- Estilos de las celdas de la tabla ---
    estilo_celda = ParagraphStyle("CeldaReporte", parent=estilos["Normal"], fontSize=8, leading=10)
    estilo_celda_derecha = ParagraphStyle("CeldaReporteDerecha", parent=estilo_celda, alignment=TA_RIGHT)
    estilo_encabezado = ParagraphStyle(
        "EncabezadoReporte", parent=estilo_celda, textColor=colors.white, fontName="Helvetica-Bold"
    )

    # --- Título y fecha de generación (hora de Colombia) ---
    elementos.append(Paragraph(escape(resultado.titulo), estilos["Title"]))
    elementos.append(Paragraph(f"Generado el {ahora_colombia().strftime('%Y-%m-%d %H:%M')}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    # --- Resumen general (totales): solo lo monetario se muestra en pesos ---
    for etiqueta, valor in resultado.resumen.items():
        es_numero = isinstance(valor, (int, float))
        texto_valor = formatear_cop(valor) if es_numero and es_resumen_monetario(etiqueta) else str(valor)
        elementos.append(Paragraph(f"<b>{escape(etiqueta)}:</b> {escape(texto_valor)}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.7 * cm))

    # --- Tabla principal del reporte ---
    if resultado.dataframe.empty:
        elementos.append(Paragraph("No hay datos para el período seleccionado.", estilos["Normal"]))
    else:
        # Primero se calculan los textos de cada celda (para medir los anchos)
        textos = []
        for _, fila in resultado.dataframe.iterrows():
            textos.append([
                formatear_cop(fila[columna]) if columna in resultado.columnas_moneda else str(fila[columna])
                for columna in columnas
            ])

        filas = [[Paragraph(escape(str(columna)), estilo_encabezado) for columna in columnas]]
        for fila_textos in textos:
            filas.append([
                Paragraph(
                    escape(texto),
                    estilo_celda_derecha if columna in resultado.columnas_moneda else estilo_celda,
                )
                for columna, texto in zip(columnas, fila_textos)
            ])

        ancho_util = pagina[0] - 2 * MARGEN_CM * cm
        tabla = Table(filas, colWidths=_anchos_de_columna(columnas, textos, ancho_util), repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_NEGRO),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F4EC")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_DORADO),
                ]
            )
        )
        elementos.append(tabla)

    documento.build(elementos)
    buffer.seek(0)
    return buffer