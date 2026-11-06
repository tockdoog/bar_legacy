# Ruta: backend/app/utils/rutas.py
# Convierte rutas relativas de la configuración (ej. "imagenes/cuentas") en rutas
# absolutas calculadas desde la raíz del backend, para que no dependan del
# directorio de trabajo del proceso (distinto en Vercel, Docker y local).

from pathlib import Path

# backend/app/utils/rutas.py -> la raíz del backend es dos niveles arriba de "utils"
RAIZ_BACKEND = Path(__file__).resolve().parents[2]


def ruta_absoluta(ruta: str) -> str:
    """Devuelve la ruta absoluta; si ya lo era (o empieza por ~), la respeta."""
    candidata = Path(ruta).expanduser()
    return str(candidata if candidata.is_absolute() else RAIZ_BACKEND / candidata)