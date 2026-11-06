# Ruta: backend/app/models/registro_log.py
# Registros del monitoreo interno guardados en la base de datos. En Vercel los
# archivos de log no persisten ni se comparten entre instancias, por eso las
# categorías seguridad, errores, sistema y negocio se guardan aquí.

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class RegistroLog(Base):
    """Una fila por evento registrado: categoría, fecha (hora de Colombia), nivel y mensaje."""
    __tablename__ = "registros_log"

    id = Column(Integer, primary_key=True)
    categoria = Column(String(20), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora_colombia)
    nivel = Column(String(10), nullable=False)
    mensaje = Column(Text, nullable=False)

    # Índices: consulta por categoría (más recientes primero) y limpieza por fecha
    __table_args__ = (
        Index("ix_registros_log_categoria_id", "categoria", "id"),
        Index("ix_registros_log_fecha", "fecha"),
    )