# Ruta: backend/scripts/respaldar_base_datos.py
# Script de mantenimiento: crea una copia de respaldo del archivo de base de
# datos SQLite antes de operaciones riesgosas (reseteos, borrados masivos,
# actualizaciones). Aplica una política de retención para no acumular
# respaldos indefinidamente y agotar espacio en disco.

from datetime import datetime
from pathlib import Path
import shutil

from _configuracion_scripts import configuracion, RAIZ_BACKEND

# --- Bloque: configuración de la política de retención ---
# Cantidad máxima de respaldos que se conservan; los más antiguos se eliminan
# automáticamente al superar este número, evitando llenar el disco con copias.
CANTIDAD_MAXIMA_RESPALDOS = 10
CARPETA_RESPALDOS = RAIZ_BACKEND / "scripts" / "respaldos"


def obtener_ruta_archivo_sqlite() -> Path | None:
    """Bloque: extrae la ruta física del archivo .db a partir de DATABASE_URL, solo si es SQLite."""
    prefijo = "sqlite:///"
    if not configuracion.DATABASE_URL.startswith(prefijo):
        return None
    ruta_relativa = configuracion.DATABASE_URL.removeprefix(prefijo)
    return (RAIZ_BACKEND / ruta_relativa).resolve()


def aplicar_politica_retencion() -> int:
    """
    Bloque: elimina los respaldos más antiguos cuando se supera el límite
    configurado. Devuelve la cantidad de archivos eliminados.
    """
    respaldos = sorted(CARPETA_RESPALDOS.glob("respaldo_*.db"), key=lambda ruta: ruta.stat().st_mtime)
    excedentes = respaldos[:-CANTIDAD_MAXIMA_RESPALDOS] if len(respaldos) > CANTIDAD_MAXIMA_RESPALDOS else []

    for respaldo_antiguo in excedentes:
        respaldo_antiguo.unlink()

    return len(excedentes)


def crear_respaldo() -> Path | None:
    """Bloque: copia el archivo de base de datos actual con marca de tiempo en su nombre."""
    ruta_bd = obtener_ruta_archivo_sqlite()
    if ruta_bd is None:
        print("DATABASE_URL no es SQLite: este script solo respalda bases de datos SQLite locales.")
        return None

    if not ruta_bd.exists():
        print(f"No se encontró el archivo de base de datos en: {ruta_bd}")
        return None

    # Bloque: se crea la carpeta de respaldos si todavía no existe
    CARPETA_RESPALDOS.mkdir(parents=True, exist_ok=True)

    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_destino = CARPETA_RESPALDOS / f"respaldo_{marca_tiempo}.db"

    # Bloque: copia binaria exacta del archivo, preservando metadatos de fecha
    shutil.copy2(ruta_bd, ruta_destino)
    return ruta_destino


def main() -> None:
    print("=" * 60)
    print("RESPALDAR BASE DE DATOS")
    print("=" * 60)

    ruta_destino = crear_respaldo()
    if ruta_destino is None:
        return

    tamano_mb = round(ruta_destino.stat().st_size / (1024 * 1024), 2)
    print(f"Respaldo creado correctamente en: {ruta_destino} ({tamano_mb} MB)")

    eliminados = aplicar_politica_retencion()
    if eliminados:
        print(f"Se eliminaron {eliminados} respaldo(s) antiguo(s) por política de retención "
              f"(máximo {CANTIDAD_MAXIMA_RESPALDOS} respaldos).")

    print("\nRecuerda: la carpeta 'scripts/respaldos' debe estar incluida en .gitignore.")


if __name__ == "__main__":
    main()