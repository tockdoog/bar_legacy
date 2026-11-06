# Ruta: backend/app/models/intento_login.py
# Intentos de inicio de sesión fallidos por dirección IP, guardados en la base de
# datos. Reemplaza al contador en memoria de slowapi, que en Vercel no se comparte
# entre instancias y por eso no frena un ataque de fuerza bruta de forma fiable.

from sqlalchemy import Column, DateTime, Index, Integer, String

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class IntentoLogin(Base):
    """Un intento fallido de login: IP de origen y momento (hora de Colombia)."""
    __tablename__ = "intentos_login"

    id = Column(Integer, primary_key=True)
    ip = Column(String(64), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora_colombia)

    # Índices: conteo por IP en una ventana de tiempo y limpieza por fecha
    __table_args__ = (
        Index("ix_intentos_login_ip_fecha", "ip", "fecha"),
        Index("ix_intentos_login_fecha", "fecha"),
    )