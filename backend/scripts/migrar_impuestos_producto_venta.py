# Ruta: backend/scripts/migrar_impuestos_producto_venta.py
# Migracion manual (unica vez): agrega a las tablas ya existentes "productos"
# y "detalles_venta" las columnas nuevas del modulo de Analisis Financiero
# (impuesto/margen propio por producto, e impuesto congelado por linea de
# venta). Necesaria porque Base.metadata.create_all() de SQLAlchemy solo crea
# TABLAS nuevas, nunca agrega columnas a tablas que ya existen. Es segura de
# ejecutar mas de una vez: cada ALTER TABLE se salta si la columna ya existe.
#
# Uso (desde dentro del contenedor del backend):
#   docker compose exec backend python3 -m scripts.migrar_impuestos_producto_venta

from sqlalchemy import inspect, text

from app.database import motor

COLUMNAS_PRODUCTOS = {
    "usar_configuracion_global": "BOOLEAN NOT NULL DEFAULT 1",
    "tipo_impuesto_propio": "VARCHAR",
    "porcentaje_impuesto_propio": "FLOAT",
    "nombre_impuesto_propio_personalizado": "VARCHAR(80)",
    "margen_utilidad_propio": "FLOAT",
}

COLUMNAS_DETALLES_VENTA = {
    "tipo_impuesto_aplicado": "VARCHAR",
    "porcentaje_impuesto_aplicado": "FLOAT DEFAULT 0",
    "etiqueta_impuesto_aplicado": "VARCHAR(80)",
}


def _agregar_columnas_faltantes(nombre_tabla: str, columnas: dict) -> None:
    inspector = inspect(motor)
    columnas_existentes = {c["name"] for c in inspector.get_columns(nombre_tabla)}

    with motor.begin() as conexion:
        for columna, definicion in columnas.items():
            if columna in columnas_existentes:
                print(f"  [omitido] {nombre_tabla}.{columna} ya existe")
                continue
            print(f"  [agregando] {nombre_tabla}.{columna} {definicion}")
            conexion.execute(text(f"ALTER TABLE {nombre_tabla} ADD COLUMN {columna} {definicion}"))


def ejecutar_migracion() -> None:
    print(f"Base de datos objetivo: {motor.url}")
    print("Migrando tabla 'productos'...")
    _agregar_columnas_faltantes("productos", COLUMNAS_PRODUCTOS)
    print("Migrando tabla 'detalles_venta'...")
    _agregar_columnas_faltantes("detalles_venta", COLUMNAS_DETALLES_VENTA)
    print("Migracion completada.")


if __name__ == "__main__":
    ejecutar_migracion()