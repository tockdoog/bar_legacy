# Ruta: backend/app/utils/exportar_excel.py
# Convierte el resultado de un reporte (DataFrame + resumen) en un archivo
# Excel (.xlsx) listo para descargar, con formato de moneda en pesos colombianos.
#
# SEGURIDAD (inyección de fórmulas): openpyxl convierte en fórmula cualquier
# texto que empiece con "=". Como los reportes incluyen texto escrito por
# usuarios (nombres de producto, motivos de anulación), esas celdas se fuerzan
# a tipo texto para que Excel nunca las ejecute.

from io import BytesIO

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.utils.formato_reportes import es_resumen_monetario
from app.utils.generador_reportes import ResultadoReporte

FORMATO_PESOS = '"$" #,##0'


def generar_excel(resultado: ResultadoReporte) -> BytesIO:
    """Construye un archivo Excel en memoria a partir de un ResultadoReporte."""
    buffer = BytesIO()
    fila_inicio_tabla = len(resultado.resumen) + 3

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resultado.dataframe.to_excel(writer, sheet_name="Reporte", index=False, startrow=fila_inicio_tabla)
        hoja = writer.sheets["Reporte"]

        # --- Título del reporte ---
        hoja["A1"] = resultado.titulo
        hoja["A1"].font = Font(size=14, bold=True)

        # --- Resumen general (totales) encima de la tabla, con pesos donde corresponde ---
        fila = 3
        for etiqueta, valor in resultado.resumen.items():
            hoja.cell(row=fila, column=1, value=etiqueta).font = Font(bold=True)
            celda_valor = hoja.cell(row=fila, column=2, value=valor)
            if isinstance(valor, (int, float)) and es_resumen_monetario(etiqueta):
                celda_valor.number_format = FORMATO_PESOS
            fila += 1

        # --- Encabezados de la tabla en negrita ---
        fila_encabezado = fila_inicio_tabla + 1
        for columna_idx in range(1, len(resultado.dataframe.columns) + 1):
            hoja.cell(row=fila_encabezado, column=columna_idx).font = Font(bold=True)

        # --- Formato de moneda en pesos colombianos para las columnas indicadas ---
        for nombre_columna in resultado.columnas_moneda:
            if nombre_columna not in resultado.dataframe.columns:
                continue
            indice_columna = resultado.dataframe.columns.get_loc(nombre_columna) + 1
            letra_columna = get_column_letter(indice_columna)
            for fila_excel in range(fila_encabezado + 1, fila_encabezado + 1 + len(resultado.dataframe)):
                hoja[f"{letra_columna}{fila_excel}"].number_format = FORMATO_PESOS

        # --- Ancho de columnas aproximado según el contenido ---
        for columna_idx, nombre_columna in enumerate(resultado.dataframe.columns, start=1):
            ancho = max(14, len(str(nombre_columna)) + 4)
            hoja.column_dimensions[get_column_letter(columna_idx)].width = ancho

        # --- Defensa contra inyección de fórmulas: todo texto que empiece con "="
        # se guarda como texto literal, nunca como fórmula ---
        for fila_celdas in hoja.iter_rows():
            for celda in fila_celdas:
                if isinstance(celda.value, str) and celda.value.startswith("="):
                    celda.data_type = "s"

    buffer.seek(0)
    return buffer