# Ruta: backend/scripts/borrar_datos_tabla.py
# Permite borrar los datos de UNA tabla específica (por ejemplo solo ventas,
# o solo compras) sin afectar el resto de la base de datos. Útil para limpiar
# datos de prueba sin tener que reiniciar todo el sistema.

from _configuracion_scripts import obtener_sesion, confirmar_accion, advertir_entorno_produccion

from app.models.venta import Venta, DetalleVenta
from app.models.compra import Compra, DetalleCompra
from app.models.producto import Producto
from app.models.categoria import Categoria
from app.models.proveedor import Proveedor
from app.models.mesa import Mesa
from app.models.promocion import Promocion, ComponentePromocion

# Mapa de opciones disponibles: nombre visible -> lista de modelos a borrar
# (se listan primero las tablas "hijas" para respetar las llaves foráneas)
OPCIONES_TABLAS = {
    "1": ("Ventas y sus detalles", [DetalleVenta, Venta]),
    "2": ("Compras y sus detalles", [DetalleCompra, Compra]),
    "3": ("Productos", [Producto]),
    "4": ("Categorías", [Categoria]),
    "5": ("Proveedores", [Proveedor]),
    "6": ("Mesas", [Mesa]),
    "7": ("Promociones y sus componentes", [ComponentePromocion, Promocion]),
}


def mostrar_menu() -> str:
    """Imprime las opciones disponibles y devuelve la opción elegida por el usuario."""
    print("\n¿Qué datos deseas borrar?")
    for clave, (nombre, _) in OPCIONES_TABLAS.items():
        print(f"  {clave}. {nombre}")
    print("  0. Cancelar")
    return input("Elige una opción: ").strip()


def borrar_tabla(modelos: list) -> None:
    """Borra todas las filas de los modelos indicados, en el orden recibido."""
    db = obtener_sesion()
    try:
        for modelo in modelos:
            cantidad = db.query(modelo).delete()
            print(f"  - {modelo.__tablename__}: {cantidad} fila(s) eliminada(s)")
        db.commit()
    except Exception as error:
        db.rollback()
        print(f"Error al borrar datos, se revirtió la operación: {error}")
    finally:
        db.close()


def main() -> None:
    print("=" * 60)
    print("BORRAR DATOS DE UNA TABLA ESPECÍFICA")
    print("=" * 60)

    advertir_entorno_produccion()

    opcion = mostrar_menu()
    if opcion == "0" or opcion not in OPCIONES_TABLAS:
        print("Operación cancelada.")
        return

    nombre, modelos = OPCIONES_TABLAS[opcion]

    if not confirmar_accion(f"¿Confirmas que quieres borrar TODOS los datos de: {nombre}?"):
        print("Operación cancelada.")
        return

    borrar_tabla(modelos)
    print("Operación completada.")


if __name__ == "__main__":
    main()