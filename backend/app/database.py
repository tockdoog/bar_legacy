# Ruta: backend/app/database.py
# Configura el motor de base de datos, la fábrica de sesiones y la clase base
# de la cual heredan todos los modelos ORM. Soporta SQLite (desarrollo local)
# y PostgreSQL en Neon (producción), incluyendo el modo serverless de Vercel.

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.config import configuracion


def _normalizar_url(url: str) -> str:
    """
    Neon entrega URLs como "postgresql://..." o "postgres://...". SQLAlchemy
    necesita indicar el driver instalado (psycopg 3), por eso se reescribe
    el prefijo. Las URLs de SQLite se dejan intactas.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


URL_BASE_DATOS = _normalizar_url(configuracion.DATABASE_URL.strip())

# Indicadores de entorno, reutilizados por main.py
ES_SQLITE = URL_BASE_DATOS.startswith("sqlite")
ES_VERCEL = bool(os.environ.get("VERCEL"))

# --- Bloque: argumentos del motor según el tipo de base de datos ---
argumentos_motor: dict = {}

if ES_SQLITE:
    # SQLite no permite por defecto compartir una conexión entre hilos
    argumentos_motor["connect_args"] = {"check_same_thread": False}
else:
    # Neon: se verifica la conexión antes de usarla (el servidor gratuito se
    # suspende por inactividad) y se desactivan las sentencias preparadas,
    # porque el pooler de Neon (PgBouncer) no las admite de forma fiable.
    argumentos_motor["pool_pre_ping"] = True
    argumentos_motor["connect_args"] = {"prepare_threshold": None, "connect_timeout": 15}

    if ES_VERCEL:
        # En serverless cada invocación es efímera: no se mantiene un pool,
        # el pooler de Neon se encarga de reutilizar conexiones.
        argumentos_motor["poolclass"] = NullPool
    else:
        argumentos_motor["pool_size"] = 5
        argumentos_motor["max_overflow"] = 5
        argumentos_motor["pool_recycle"] = 300

motor = create_engine(URL_BASE_DATOS, **argumentos_motor)

# --- Fábrica de sesiones: cada petición obtiene su propia sesión independiente ---
SesionLocal = sessionmaker(autocommit=False, autoflush=False, bind=motor)

# --- Clase base para los modelos ORM (Usuario, Producto, etc.) ---
Base = declarative_base()


def obtener_db():
    """
    Generador que entrega una sesión de base de datos por cada petición
    y la cierra automáticamente al finalizar, evitando fugas de conexiones.
    """
    db = SesionLocal()
    try:
        yield db
    finally:
        db.close()