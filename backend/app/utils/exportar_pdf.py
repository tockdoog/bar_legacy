# Ruta: backend/app/utils/exportar_pdf.py
# Convierte el resultado de un reporte (DataFrame + resumen) en un archivo PDF
# listo para descargar, usando ReportLab y montos formateados en pesos colombianos.

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.utils.generador_reportes import ResultadoReporte

# Colores de la identidad visual del sistema, reutilizados en el encabezado de la tabla
COLOR_ROJO = colors.HexColor("#C8102E")
COLOR_NEGRO = colors.HexColor("#0A0A0A")


def _formatear_cop(valor: float) -> str:
    """Formatea un número como pesos colombianos con punto como separador de miles."""
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def _es_columna_monetaria(etiqueta: str) -> bool:
    """Determina si una etiqueta del resumen representa un valor en dinero (para formatearlo como COP)."""
    palabras_clave = ("monto", "total", "ganancia", "costo", "valor")
    return any(palabra in etiqueta.lower() for palabra in palabras_clave)


def generar_pdf(resultado: ResultadoReporte) -> BytesIO:
    """Construye un archivo PDF en memoria a partir de un ResultadoReporte."""
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm)
    estilos = getSampleStyleSheet()
    elementos = []

    # --- Título y fecha de generación ---
    elementos.append(Paragraph(resultado.titulo, estilos["Title"]))
    elementos.append(Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}", estilos["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    # --- Resumen general (totales) ---
    for etiqueta, valor in resultado.resumen.items():
        es_numero = isinstance(valor, (int, float))
        texto_valor = _formatear_cop(valor) if es_numero and _es_columna_monetaria(etiqueta) else str(valor)
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
                    fila_textos.append(_formatear_cop(valor))
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
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F0")]),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, COLOR_ROJO),
                ]
            )
        )
        elementos.append(tabla)

    documento.build(elementos)
    buffer.seek(0)
    return buffer