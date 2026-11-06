# Ruta: backend/app/utils/migraciones.py
# Aplica automáticamente, en cada arranque, cambios de esquema menores (agregar
# columnas) sobre bases creadas con una versión anterior del modelo. Es seguro
# ejecutarlo siempre: si la columna ya existe, no hace nada.
#
# CORRECCIÓN: en PostgreSQL usa "ADD COLUMN IF NOT EXISTS" y tolera que otra
# instancia de Vercel haya agregado la columna al mismo tiempo.

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("uvicorn.error")

# Columnas que pudieron faltar en bases creadas antes de existir en el modelo.
# Para una migración futura agrega una tupla nueva (tabla, columna, definición_sql);
# nunca modifiques ni borres las ya usadas.
COLUMNAS_A_VERIFICAR: list[tuple[str, str, str]] = [
    ("usuarios", "permisos", "TEXT"),
]


def _columnas_de_tabla(motor: Engine, tabla: str) -> list[str]:
    """Lee las columnas reales de una tabla con un inspector nuevo (sin caché)."""
    return [info["name"] for info in inspect(motor).get_columns(tabla)]


def _sentencia_agregar_columna(motor: Engine, tabla: str, columna: str, definicion_sql: str):
    """Construye el ALTER TABLE adecuado al motor. Los nombres vienen de la lista fija de arriba."""
    modificador = "ADD COLUMN IF NOT EXISTS" if motor.dialect.name == "postgresql" else "ADD COLUMN"
    return text(f"ALTER TABLE {tabla} {modificador} {columna} {definicion_sql}")


def aplicar_migraciones_pendientes(motor: Engine) -> None:
    """Agrega las columnas de COLUMNAS_A_VERIFICAR que aún no existan en la base de datos."""
    for tabla, columna, definicion_sql in COLUMNAS_A_VERIFICAR:
        if not inspect(motor).has_table(tabla):
            continue  # create_all() ya la crea con la columna incluida

        if columna in _columnas_de_tabla(motor, tabla):
            continue

        try:
            with motor.begin() as conexion:
                conexion.execute(_sentencia_agregar_columna(motor, tabla, columna, definicion_sql))
            logger.info(f"Migración aplicada: columna '{columna}' agregada a '{tabla}'")
        except SQLAlchemyError:
            # Si otra instancia ya la agregó, no hay problema; si sigue faltando, el error es real
            if columna not in _columnas_de_tabla(motor, tabla):
                raise