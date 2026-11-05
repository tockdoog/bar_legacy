# Ruta: backend/scripts/limpiar_logs_antiguos.py
# Script de mantenimiento: revisa la carpeta de logs configurada en el .env
# (CARPETA_LOGS) y elimina archivos de log rotados que superen la política
# de retención definida en LOG_BACKUP_COUNT, liberando espacio en disco.

from pathlib import Path

from _configuracion_scripts import configuracion, confirmar_accion


def obtener_carpeta_logs() -> Path:
    """Bloque: expande el símbolo '~' de CARPETA_LOGS al home real del sistema operativo."""
    return Path(configuracion.CARPETA_LOGS).expanduser().resolve()


def listar_archivos_log(carpeta: Path) -> list[Path]:
    """Bloque: lista todos los archivos de log y sus rotaciones (.log, .log.1, .log.2, ...)."""
    if not carpeta.exists():
        return []
    return sorted(carpeta.glob("*.log*"), key=lambda ruta: ruta.stat().st_mtime, reverse=True)


def calcular_archivos_a_eliminar(archivos: list[Path]) -> list[Path]:
    """
    Bloque: conserva únicamente el archivo activo más reciente de cada log
    más la cantidad de rotaciones permitidas por LOG_BACKUP_COUNT; el resto
    se marca para eliminación.
    """
    limite = 1 + configuracion.LOG_BACKUP_COUNT  # archivo activo + rotaciones permitidas
    if len(archivos) <= limite:
        return []
    return archivos[limite:]


def main() -> None:
    print("=" * 60)
    print("LIMPIAR LOGS ANTIGUOS")
    print("=" * 60)

    carpeta_logs = obtener_carpeta_logs()
    print(f"Carpeta de logs configurada: {carpeta_logs}")

    archivos = listar_archivos_log(carpeta_logs)
    if not archivos:
        print("No se encontraron archivos de log en esa carpeta.")
        return

    a_eliminar = calcular_archivos_a_eliminar(archivos)
    if not a_eliminar:
        print(f"Todo en orden: hay {len(archivos)} archivo(s) de log, dentro del límite permitido "
              f"({configuracion.LOG_BACKUP_COUNT} rotaciones + archivo activo).")
        return

    print(f"\nSe encontraron {len(a_eliminar)} archivo(s) de log que exceden la política de retención:")
    for archivo in a_eliminar:
        tamano_kb = round(archivo.stat().st_size / 1024, 1)
        print(f"  - {archivo.name} ({tamano_kb} KB)")

    if not confirmar_accion("¿Confirmas que quieres eliminar estos archivos de log antiguos?"):
        print("Operación cancelada.")
        return

    for archivo in a_eliminar:
        archivo.unlink(missing_ok=True)

    print(f"Se eliminaron {len(a_eliminar)} archivo(s) de log antiguos correctamente.")


if __name__ == "__main__":
    main()