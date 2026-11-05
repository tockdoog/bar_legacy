# Ruta: backend/scripts/resetear_base_datos.py
# Borra TODAS las tablas de la base de datos y las vuelve a crear desde cero
# a partir de los modelos definidos en app/models. Uso exclusivo de desarrollo:
# pide doble confirmación y bloquea la ejecución accidental en producción.

from _configuracion_scripts import Base, motor, obtener_sesion, confirmar_accion, advertir_entorno_produccion

# Se importan todos los modelos para que queden registrados en Base.metadata
# antes de crear las tablas; si un modelo no se importa aquí, SQLAlchemy no
# sabe que existe y no lo crea.
from app.models.usuario import Usuario  # noqa: F401
from app.models.producto import Producto  # noqa: F401
from app.models.categoria import Categoria  # noqa: F401
from app.models.proveedor import Proveedor  # noqa: F401
from app.models.compra import Compra, DetalleCompra  # noqa: F401
from app.models.venta import Venta, DetalleVenta  # noqa: F401
from app.models.mesa import Mesa  # noqa: F401
from app.models.promocion import Promocion, ComponentePromocion  # noqa: F401
from app.suscripcion.models import *  # noqa: F401,F403

from app.utils.inicializar_admin import crear_administrador_inicial


def resetear() -> None:
    """Elimina y recrea todas las tablas, luego crea el usuario administrador inicial."""
    print("Eliminando todas las tablas existentes...")
    Base.metadata.drop_all(bind=motor)

    print("Creando tablas nuevas a partir de los modelos actuales...")
    Base.metadata.create_all(bind=motor)

    print("Creando usuario administrador inicial...")
    db = obtener_sesion()
    try:
        crear_administrador_inicial(db)
    finally:
        db.close()

    print("Base de datos reiniciada correctamente.")


def main() -> None:
    print("=" * 60)
    print("RESETEAR BASE DE DATOS COMPLETA")
    print("Esta acción BORRA TODOS los datos: usuarios, productos, ventas,")
    print("compras, mesas, promociones y proveedores. No se puede deshacer.")
    print("=" * 60)

    advertir_entorno_produccion()

    if not confirmar_accion("¿Confirmas que quieres borrar y recrear TODA la base de datos?"):
        print("Operación cancelada.")
        return

    # Segunda confirmación deliberadamente redundante: esta acción es irreversible
    if not confirmar_accion("Última confirmación: ¿REALMENTE quieres continuar?"):
        print("Operación cancelada.")
        return

    resetear()


if __name__ == "__main__":
    main()