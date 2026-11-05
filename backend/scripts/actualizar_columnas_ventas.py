# Ruta: backend/scripts/actualizar_columnas_ventas.py
# Migración manual para bases de datos SQLite ya existentes: agrega las
# columnas nuevas que necesita la tabla "ventas" (método de pago y auditoría
# de anulación) SIN borrar ningún dato. SQLAlchemy solo crea tablas nuevas
# con create_all(); no altera tablas que ya existen, por eso este script usa
# sentencias ALTER TABLE directas y es seguro ejecutarlo varias veces (revisa
# primero qué columnas ya existen antes de intentar agregarlas).

from _configuracion_scripts import motor, advertir_entorno_produccion
from sqlalchemy import text, inspect


# Columnas que este script debe garantizar que existan en la tabla "ventas".
# Cada tupla es (nombre_columna, definición_sql_para_agregarla).
COLUMNAS_REQUERIDAS = [
    ("metodo_pago", "VARCHAR"),
    ("motivo_anulacion", "VARCHAR"),
    ("usuario_anulacion_id", "INTEGER"),
    ("fecha_anulacion", "DATETIME"),
]


def obtener_columnas_actuales() -> set[str]:
    """Devuelve el conjunto de nombres de columnas que ya tiene la tabla 'ventas'."""
    inspector = inspect(motor)
    return {columna["name"] for columna in inspector.get_columns("ventas")}


def migrar() -> None:
    """Agrega, una por una, las columnas que falten en la tabla 'ventas'."""
    columnas_actuales = obtener_columnas_actuales()
    columnas_agregadas = []

    with motor.begin() as conexion:
        for nombre_columna, tipo_sql in COLUMNAS_REQUERIDAS:
            if nombre_columna in columnas_actuales:
                print(f"  - '{nombre_columna}' ya existe, se omite.")
                continue

            print(f"  - Agregando columna '{nombre_columna}' ({tipo_sql})...")
            conexion.execute(text(f"ALTER TABLE ventas ADD COLUMN {nombre_columna} {tipo_sql}"))
            columnas_agregadas.append(nombre_columna)

    if columnas_agregadas:
        print(f"\nColumnas agregadas correctamente: {', '.join(columnas_agregadas)}")
    else:
        print("\nLa tabla 'ventas' ya estaba al día. No se hicieron cambios.")


def main() -> None:
    print("=" * 60)
    print("ACTUALIZAR TABLA 'ventas' (metodo de pago + anulacion)")
    print("Este script agrega columnas nuevas sin borrar datos existentes.")
    print("=" * 60)

    advertir_entorno_produccion()

    try:
        migrar()
    except Exception as error:
        print(f"\nOcurrió un error durante la migración: {error}")
        print("No se perdieron datos: cada columna se agrega en su propia operación.")
        raise

    print("\nMigración completada. Ya puedes iniciar el backend normalmente.")


if __name__ == "__main__":
    main()