# Ruta: backend/app/models/bloqueo_mesa.py
# Bloqueo colaborativo de mesas guardado en la base de datos. Reemplaza al
# WebSocket (que Vercel no soporta): quien abre la cuenta de una mesa toma el
# bloqueo y lo renueva con un "latido" periódico; si deja de renovarlo (cerró el
# navegador, perdió conexión) expira solo a los TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS.

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class BloqueoMesa(Base):
    """Una fila por mesa bloqueada: quién la atiende, desde cuándo y su último latido."""
    __tablename__ = "bloqueos_mesa"

    mesa_id = Column(Integer, ForeignKey("mesas.id", ondelete="CASCADE"), primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre_completo = Column(String(120), nullable=False)
    nombre_usuario = Column(String(50), nullable=False)
    desde = Column(DateTime, nullable=False, default=ahora_colombia)
    ultimo_latido = Column(DateTime, nullable=False, default=ahora_colombia)