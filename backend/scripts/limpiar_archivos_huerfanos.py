# Ruta: backend/scripts/limpiar_archivos_huerfanos.py
# Script de mantenimiento: busca imágenes de productos que existen físicamente
# en la carpeta de uploads pero que ya no están referenciadas por ningún
# producto en la base de datos (por ejemplo, tras editar o borrar un producto
# sin que la imagen anterior se haya eliminado). Solo actúa sobre uploads de
# productos, respetando la ruta definida en CARPETA_IMAGENES_PRODUCTOS.

from pathlib import Path

from _configuracion_scripts import configuracion, RAIZ_BACKEND, obtener_sesion, confirmar_accion
from app.models.producto import Producto


def obtener_carpeta_uploads() -> Path:
    """Bloque: resuelve la ruta absoluta de la carpeta de imágenes de productos."""
    return (RAIZ_BACKEND / configuracion.CARPETA_IMAGENES_PRODUCTOS).resolve()


def obtener_imagenes_referenciadas() -> set[str]:
    """Bloque: consulta la base de datos y devuelve el conjunto de nombres de archivo en uso."""
    db = obtener_sesion()
    try:
        rutas = db.query(Producto.imagen_url).filter(Producto.imagen_url.isnot(None)).all()
        # Se guarda solo el nombre del archivo (no la ruta completa) para comparar con disco
        return {Path(ruta[0]).name for ruta in rutas if ruta[0]}
    finally:
        db.close()


def obtener_archivos_huerfanos(carpeta: Path, referenciadas: set[str]) -> list[Path]:
    """Bloque: compara los archivos físicos contra las referencias en base de datos."""
    if not carpeta.exists():
        return []
    return [
        archivo for archivo in carpeta.iterdir()
        if archivo.is_file() and archivo.name not in referenciadas
    ]


def main() -> None:
    print("=" * 60)
    print("LIMPIAR IMÁGENES HUÉRFANAS DE PRODUCTOS")
    print("=" * 60)

    carpeta_uploads = obtener_carpeta_uploads()
    print(f"Carpeta de imágenes: {carpeta_uploads}")

    referenciadas = obtener_imagenes_referenciadas()
    huerfanos = obtener_archivos_huerfanos(carpeta_uploads, referenciadas)

    if not huerfanos:
        print("No se encontraron imágenes huérfanas. Todo está en orden.")
        return

    print(f"\nSe encontraron {len(huerfanos)} archivo(s) huérfano(s):")
    tamano_total_bytes = 0
    for archivo in huerfanos:
        tamano_total_bytes += archivo.stat().st_size
        print(f"  - {archivo.name}")

    tamano_total_mb = round(tamano_total_bytes / (1024 * 1024), 2)
    print(f"\nEspacio total que se liberaría: {tamano_total_mb} MB")

    if not confirmar_accion("¿Confirmas que quieres eliminar estos archivos huérfanos?"):
        print("Operación cancelada.")
        return

    for archivo in huerfanos:
        archivo.unlink(missing_ok=True)

    print(f"Se eliminaron {len(huerfanos)} imagen(es) huérfana(s) correctamente.")


if __name__ == "__main__":
    main()