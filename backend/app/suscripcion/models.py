# Ruta: backend/app/suscripcion/models.py
# Modelo de base de datos del módulo de suscripción: el registro único que
# controla el ciclo de pago mensual y el estado de bloqueo del sistema. Las
# cuentas/medios de pago del proveedor ya NO viven en base de datos: se
# definen como configuración fija en app/suscripcion/cuentas_proveedor.py,
# porque las administra únicamente el proveedor del software, no el
# administrador del negocio que usa el sistema.

from sqlalchemy import Column, Integer, DateTime

from app.database import Base


class Suscripcion(Base):
    """Registro único que controla el ciclo de pago mensual y el estado de bloqueo del sistema."""
    __tablename__ = "suscripcion"

    id = Column(Integer, primary_key=True, index=True)

    # Fecha en que inició el ciclo de pago actual
    fecha_inicio = Column(DateTime, nullable=False)

    # Fecha a partir de la cual el sistema se bloquea automáticamente si no se renueva
    fecha_vencimiento = Column(DateTime, nullable=False)

    # --- Protección contra fuerza bruta sobre la contraseña maestra de desbloqueo ---
    intentos_fallidos = Column(Integer, default=0, nullable=False)
    bloqueado_hasta = Column(DateTime, nullable=True)
    fecha_ultimo_desbloqueo = Column(DateTime, nullable=True)