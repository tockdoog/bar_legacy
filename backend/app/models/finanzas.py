# Ruta: backend/app/models/finanzas.py
# Modelo de base de datos para la configuración financiera del negocio: tipo de
# impuesto activo (sin impuesto, IVA, INC o personalizado), su porcentaje, y el
# margen de utilidad deseado. Patrón de "una sola fila" (id=1).
# CORRECCIÓN: fecha_actualizacion usa la hora local de Colombia.

import enum

from sqlalchemy import Column, Integer, Float, String, DateTime, Enum

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class TipoImpuesto(str, enum.Enum):
    """Tipos de impuesto que el administrador puede aplicar sobre el precio de venta."""
    SIN_IMPUESTO = "sin_impuesto"
    IVA = "iva"
    INC = "inc"
    PERSONALIZADO = "personalizado"


# Etiquetas legibles en español para pantalla, reportes y selectores del frontend
ETIQUETAS_TIPO_IMPUESTO = {
    TipoImpuesto.SIN_IMPUESTO: "Sin impuesto",
    TipoImpuesto.IVA: "IVA (Colombia)",
    TipoImpuesto.INC: "INC - Impuesto Nacional al Consumo (Colombia)",
    TipoImpuesto.PERSONALIZADO: "Impuesto personalizado",
}

# Porcentajes de referencia (Colombia), solo como sugerencia editable en el frontend
PORCENTAJES_REFERENCIA = {
    TipoImpuesto.SIN_IMPUESTO: 0.0,
    TipoImpuesto.IVA: 19.0,
    TipoImpuesto.INC: 8.0,
    TipoImpuesto.PERSONALIZADO: 0.0,
}


class ConfiguracionFinanciera(Base):
    """Configuración financiera del negocio (impuestos y margen de utilidad deseado)."""
    __tablename__ = "configuracion_financiera"

    id = Column(Integer, primary_key=True, index=True)

    # Impuesto activo
    tipo_impuesto = Column(Enum(TipoImpuesto), nullable=False, default=TipoImpuesto.SIN_IMPUESTO)
    porcentaje_impuesto = Column(Float, nullable=False, default=0.0)
    nombre_impuesto_personalizado = Column(String(80), nullable=True)

    # Margen de utilidad deseado por defecto (%) y margen mínimo saludable (%)
    margen_utilidad_deseado = Column(Float, nullable=False, default=30.0)
    margen_minimo_saludable = Column(Float, nullable=False, default=15.0)

    fecha_actualizacion = Column(DateTime, default=ahora_colombia, onupdate=ahora_colombia)