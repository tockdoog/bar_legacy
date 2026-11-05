# Ruta: backend/app/utils/migraciones.py
# Aplica automáticamente, en cada arranque del servidor, cambios de esquema
# menores (agregar columnas) sobre bases de datos SQLite creadas con una
# versión anterior del modelo. Evita depender de ejecutar scripts sueltos a
# mano en cada entorno (local, Docker, servidor del cliente). Es seguro
# ejecutarlo en cada arranque: si la columna ya existe, no hace nada.

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("uvicorn.error")

# Lista de columnas que pudieron faltar en bases de datos creadas antes de
# que existiera esa columna en el modelo actual. Cada entrada agrega UNA
# columna nueva a una tabla ya existente.
#
# Para una migración futura (ej. agregar otra columna a otra tabla): agrega
# aquí una tupla nueva (tabla, columna, definición_sql). Nunca modifiques ni
# borres las entradas ya usadas, para que el historial quede claro y no se
# repita trabajo ya aplicado en las bases de datos de producción.
COLUMNAS_A_VERIFICAR: list[tuple[str, str, str]] = [
    ("usuarios", "permisos", "TEXT"),
]


def aplicar_migraciones_pendientes(motor: Engine) -> None:
    """Agrega las columnas listadas en COLUMNAS_A_VERIFICAR si aún no existen en la base de datos."""
    inspector = inspect(motor)

    for tabla, columna, definicion_sql in COLUMNAS_A_VERIFICAR:
        if not inspector.has_table(tabla):
            # La tabla todavía no existe: Base.metadata.create_all() ya la
            # crea con la columna incluida, así que no hay nada que migrar.
            continue

        columnas_actuales = [info["name"] for info in inspector.get_columns(tabla)]
        if columna in columnas_actuales:
            continue

        with motor.connect() as conexion:
            conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion_sql}"))
            conexion.commit()

        logger.info(f"Migración aplicada: se agregó la columna '{columna}' a la tabla '{tabla}'")