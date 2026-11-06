# Ruta: backend/app/utils/exportar_pdf.py
# Convierte el resultado de un reporte (DataFrame + resumen) en un archivo PDF
# listo para descargar, usando ReportLab y montos formateados en pesos colombianos.
#
# CORRECCIONES: el resumen solo da formato de pesos a los valores realmente
# monetarios (ver formato_reportes.py) y la fecha de generación usa la hora de
# Colombia (ahora_colombia) en vez de la hora del servidor.

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.utils.formato_reportes import es_resumen_monetario, formatear_cop
from app.utils.generador_reportes import ResultadoReporte
from app.utils.zona_horaria import ahora_colombia

# Colores de la identidad visual del sistema, reutilizados en el encabezado de la tabla
COLOR_DORADO = colors.HexColor("#C9A24B")
COLOR_NEGRO = colors.HexColor("#1C1C1C")


def generar_pdf(resultado: ResultadoReporte) -> BytesIO:
    """Construye un archivo PDF en memoria a partir de un ResultadoReporte."""
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm)
    estilos = getSampleStyleSheet()
    elementos = []

    # --- Título y fecha de generación (hora de Colombia) ---
    elementos.append(Paragraph(resultado.titulo, estilos["Title"]))
    elementos.append(Paragraph(f"Generado el {ahora_colombia().strftime('%Y-%m-%d %H:%M')}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    # --- Resumen general (totales): solo lo monetario se muestra en pesos ---
    for etiqueta, valor in resultado.resumen.items():
        es_numero = isinstance(valor, (int, float))
        texto_valor = formatear_cop(valor) if es_numero and es_resumen_monetario(etiqueta) else str(valor)
        elementos.append(Paragraph(f"<b>{etiqueta}:</b> {texto_valor}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.7 * cm))

    # --- Tabla principal del reporte ---
    if resultado.dataframe.empty:
        elementos.append(Paragraph("No hay datos para el período seleccionado.", estilos["Normal"]))
    else:
        columnas = list(resultado.dataframe.columns)
        filas = [columnas]
        for _, fila in resultado.dataframe.iterrows():
            fila_textos = []
            for columna in columnas:
                valor = fila[columna]
                if columna in resultado.columnas_moneda:
                    fila_textos.append(formatear_cop(valor))
                else:
                    fila_textos.append(str(valor))
            filas.append(fila_textos)

        tabla = Table(filas, repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_NEGRO),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F4EC")]),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
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