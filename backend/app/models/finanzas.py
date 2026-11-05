# Ruta: backend/app/models/finanzas.py
# Modelo de base de datos para la configuracion financiera del negocio:
# tipo de impuesto activo (sin impuesto, IVA, INC o personalizado), su
# porcentaje, y el margen de utilidad deseado usado como base para las
# recomendaciones de precio. Sigue el patron de "una sola fila" (id=1),
# igual que ConfiguracionSuscripcion: siempre existe un unico registro que
# se lee y actualiza, nunca se crean filas nuevas. No representa ningun
# nicho de negocio: aplica a cualquier tipo de comercio en Colombia.

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Float, String, DateTime, Enum

from app.database import Base


class TipoImpuesto(str, enum.Enum):
    """Tipos de impuesto que el administrador puede aplicar sobre el precio de venta."""
    SIN_IMPUESTO = "sin_impuesto"
    IVA = "iva"
    INC = "inc"
    PERSONALIZADO = "personalizado"


# Etiquetas legibles en español para mostrar en pantalla, reportes y select del frontend
ETIQUETAS_TIPO_IMPUESTO = {
    TipoImpuesto.SIN_IMPUESTO: "Sin impuesto",
    TipoImpuesto.IVA: "IVA (Colombia)",
    TipoImpuesto.INC: "INC - Impuesto Nacional al Consumo (Colombia)",
    TipoImpuesto.PERSONALIZADO: "Impuesto personalizado",
}

# Porcentajes de referencia (Colombia), usados SOLO como sugerencia inicial en
# el frontend al elegir un tipo de impuesto. El administrador puede editarlos
# libremente porque la tarifa vigente puede cambiar segun la ley tributaria o
# el tipo de negocio; el motor de calculo nunca asume un valor fijo (siempre
# usa el porcentaje guardado en ConfiguracionFinanciera).
PORCENTAJES_REFERENCIA = {
    TipoImpuesto.SIN_IMPUESTO: 0.0,
    TipoImpuesto.IVA: 19.0,
    TipoImpuesto.INC: 8.0,
    TipoImpuesto.PERSONALIZADO: 0.0,
}


class ConfiguracionFinanciera(Base):
    """
    Tabla de configuracion financiera del negocio (impuestos y margen de
    utilidad deseado). Es una tabla nueva: SQLAlchemy la crea sola al
    iniciar el backend (create_all), sin requerir ninguna migracion manual.
    """
    __tablename__ = "configuracion_financiera"

    id = Column(Integer, primary_key=True, index=True)

    # --- Impuesto activo ---
    tipo_impuesto = Column(Enum(TipoImpuesto), nullable=False, default=TipoImpuesto.SIN_IMPUESTO)
    porcentaje_impuesto = Column(Float, nullable=False, default=0.0)
    # Solo se usa cuando tipo_impuesto == PERSONALIZADO
    nombre_impuesto_personalizado = Column(String(80), nullable=True)

    # --- Margen de utilidad deseado por defecto (%) ---
    # Se usa en las recomendaciones de precio cuando el administrador no
    # indica un margen personalizado en una consulta puntual.
    margen_utilidad_deseado = Column(Float, nullable=False, default=30.0)

    # --- Margen minimo saludable (%) ---
    # Por debajo de este umbral se genera una advertencia de "bajo margen"
    # en el analisis de productos, aunque el producto no se venda en perdida.
    margen_minimo_saludable = Column(Float, nullable=False, default=15.0)

    fecha_actualizacion = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )