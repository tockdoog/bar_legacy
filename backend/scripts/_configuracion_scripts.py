# Ruta: backend/scripts/_configuracion_scripts.py
# Módulo interno compartido por todos los scripts de mantenimiento del backend.
# No es un endpoint ni se expone por HTTP: solo se ejecuta manualmente desde consola.
# Se encarga de: registrar la carpeta "app" en el PYTHONPATH, entregar una sesión
# de base de datos independiente y ofrecer utilidades comunes de seguridad
# (confirmación explícita y advertencia especial para entorno de producción).

import sys
from pathlib import Path

# --- Bloque: ajuste de PYTHONPATH ---
# Los scripts viven en backend/scripts/, pero el paquete "app" vive en backend/app.
# Sin este ajuste, ejecutar "python scripts/algo.py" fallaría al hacer "from app...".
RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import configuracion  # noqa: E402
from app.database import SesionLocal, motor, Base  # noqa: E402


def obtener_sesion():
    """Devuelve una sesión de base de datos independiente del ciclo de vida de FastAPI."""
    return SesionLocal()


def confirmar_accion(mensaje: str) -> bool:
    """
    Bloque de seguridad: exige que el operador escriba exactamente "SI" en
    mayúsculas antes de ejecutar una acción destructiva o irreversible.
    Cualquier otra respuesta (incluido Enter vacío) cancela la operación.
    """
    respuesta = input(f"\n{mensaje}\nEscribe 'SI' en mayúsculas para confirmar: ").strip()
    return respuesta == "SI"


def advertir_entorno_produccion() -> None:
    """
    Bloque de seguridad: si el .env tiene ENTORNO=produccion, se muestra una
    advertencia fuerte y se exige una confirmación adicional, para evitar que
    un script de mantenimiento afecte datos reales del negocio por confusión
    de entorno (desarrollo vs. producción).
    """
    if configuracion.es_produccion:
        print("=" * 60)
        print("ATENCION: ENTORNO=produccion detectado en el archivo .env")
        print("Este script puede modificar, borrar o limpiar datos reales.")
        print("=" * 60)
        if not confirmar_accion("¿Confirmas que quieres continuar en PRODUCCION?"):
            print("Operación cancelada por seguridad.")
            sys.exit(0)