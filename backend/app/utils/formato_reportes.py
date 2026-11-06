# Ruta: backend/app/utils/formato_reportes.py
# Reglas de formato compartidas por las exportaciones de reportes (Excel y PDF):
# decide qué valores del resumen son dinero. Antes cada exportador usaba una
# regla distinta y "Unidades totales" o "Total de escaneos" salían como pesos.

import re

# Etiquetas del resumen que representan dinero. Es una lista explícita (no
# "cualquier etiqueta con 'total'") para no formatear conteos como pesos.
_PATRON_MONEDA = re.compile(
    r"monto|ganancia|costo|valor|ventas totales|total (en|vendido|anulado)",
    re.IGNORECASE,
)


def es_resumen_monetario(etiqueta: str) -> bool:
    """Indica si la etiqueta de un dato del resumen corresponde a un valor en pesos."""
    return bool(_PATRON_MONEDA.search(etiqueta))


def formatear_cop(valor: float | None) -> str:
    """Formatea un número como pesos colombianos con punto como separador de miles."""
    return "$ " + f"{(valor or 0):,.0f}".replace(",", ".")