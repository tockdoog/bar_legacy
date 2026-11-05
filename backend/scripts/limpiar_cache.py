# Ruta: backend/scripts/limpiar_cache.py
# Script de mantenimiento: elimina archivos y carpetas de caché generados por
# Python y herramientas de desarrollo (__pycache__, .pyc, .pytest_cache, etc.).
# No toca código fuente ni datos: solo archivos que Python regenera automáticamente.

import shutil
from pathlib import Path

from _configuracion_scripts import RAIZ_BACKEND

# --- Bloque: patrones de carpetas de caché a eliminar ---
CARPETAS_CACHE = ["__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"]

# --- Bloque: extensiones de archivos de caché/compilados a eliminar ---
EXTENSIONES_CACHE = [".pyc", ".pyo"]


def limpiar_carpetas_cache(raiz: Path) -> int:
    """Bloque: recorre recursivamente el proyecto y elimina carpetas de caché conocidas."""
    total_eliminadas = 0
    for nombre_carpeta in CARPETAS_CACHE:
        for ruta_carpeta in raiz.rglob(nombre_carpeta):
            if ruta_carpeta.is_dir():
                shutil.rmtree(ruta_carpeta, ignore_errors=True)
                total_eliminadas += 1
    return total_eliminadas


def limpiar_archivos_compilados(raiz: Path) -> int:
    """Bloque: elimina archivos compilados sueltos (.pyc, .pyo) fuera de __pycache__."""
    total_eliminados = 0
    for extension in EXTENSIONES_CACHE:
        for ruta_archivo in raiz.rglob(f"*{extension}"):
            ruta_archivo.unlink(missing_ok=True)
            total_eliminados += 1
    return total_eliminados


def main() -> None:
    print("=" * 60)
    print("LIMPIAR CACHÉ DE PYTHON Y HERRAMIENTAS DE DESARROLLO")
    print("=" * 60)

    carpetas_eliminadas = limpiar_carpetas_cache(RAIZ_BACKEND)
    archivos_eliminados = limpiar_archivos_compilados(RAIZ_BACKEND)

    print(f"Carpetas de caché eliminadas: {carpetas_eliminadas}")
    print(f"Archivos compilados eliminados: {archivos_eliminados}")
    print("\nLimpieza completada. Esto no afecta datos ni configuración del sistema.")


if __name__ == "__main__":
    main()