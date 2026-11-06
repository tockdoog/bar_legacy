# Ruta: backend/app/models/producto.py
# Modelo de base de datos para los productos del inventario general del negocio.
# Cada producto puede usar la configuración global de impuesto y margen
# (módulo de Análisis Financiero) o tener la suya si "usar_configuracion_global"
# es False. CORRECCIÓN: fecha_creacion usa la hora local de Colombia.

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.finanzas import TipoImpuesto
from app.utils.zona_horaria import ahora_colombia


class Producto(Base):
    """Tabla de productos disponibles para la venta y control de inventario."""
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)

    # Código de barras: usado para registrar y buscar productos mediante escáner
    codigo_barras = Column(String(64), unique=True, index=True, nullable=True)

    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="productos")

    # Presentación libre (ej: unidad, paquete, caja)
    presentacion = Column(String(60), nullable=False, default="unidad")

    # Precios en pesos colombianos (COP)
    precio_compra = Column(Float, nullable=False, default=0)
    precio_venta = Column(Float, nullable=False, default=0)

    stock_actual = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=0)

    # Configuración propia de impuesto y margen (Análisis Financiero)
    usar_configuracion_global = Column(Boolean, nullable=False, default=True)
    tipo_impuesto_propio = Column(Enum(TipoImpuesto), nullable=True)
    porcentaje_impuesto_propio = Column(Float, nullable=True)
    nombre_impuesto_propio_personalizado = Column(String(80), nullable=True)
    margen_utilidad_propio = Column(Float, nullable=True)

    # Ruta pública de la imagen (ej: "/uploads/productos/<uuid>.jpg"). El archivo
    # vive en la tabla imagenes_producto (ver models/imagen_producto.py).
    imagen_url = Column(String(255), nullable=True)

    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(DateTime, default=ahora_colombia)