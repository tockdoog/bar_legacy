# Ruta: backend/app/models/producto.py
# Modelo de base de datos para los productos del inventario general del negocio.
# Cada producto puede usar la configuracion global de impuesto y margen
# (definida en el modulo de Analisis Financiero), o tener su PROPIA
# configuracion de impuesto y margen si "usar_configuracion_global" es False
# (ej: un producto exento de impuesto mientras el resto del negocio cobra IVA).

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.finanzas import TipoImpuesto


class Producto(Base):
    """Tabla de productos disponibles para la venta y control de inventario."""
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)

    # Código de barras: usado para registrar y buscar productos mediante escáner
    codigo_barras = Column(String(64), unique=True, index=True, nullable=True)

    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="productos")

    # Presentación libre (ej: unidad, paquete, caja) para no atar el sistema a un solo tipo de negocio
    presentacion = Column(String(60), nullable=False, default="unidad")

    # Precios en pesos colombianos (COP), almacenados como números enteros sin decimales
    precio_compra = Column(Float, nullable=False, default=0)
    precio_venta = Column(Float, nullable=False, default=0)

    stock_actual = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=0)

    # --- Configuracion propia de impuesto y margen (Analisis Financiero) ---
    # Si "usar_configuracion_global" es True (valor por defecto), el producto
    # hereda el impuesto y el margen definidos en ConfiguracionFinanciera
    # (modulo de Analisis Financiero). Si es False, se usan los campos
    # "propio" de abajo en su lugar. Todos con default para no romper
    # productos ya existentes al agregar esta columna.
    usar_configuracion_global = Column(Boolean, nullable=False, default=True)
    tipo_impuesto_propio = Column(Enum(TipoImpuesto), nullable=True)
    porcentaje_impuesto_propio = Column(Float, nullable=True)
    nombre_impuesto_propio_personalizado = Column(String(80), nullable=True)
    margen_utilidad_propio = Column(Float, nullable=True)

    # Ruta relativa de la imagen del producto (ej: "/uploads/productos/<uuid>.jpg").
    # Se guarda solo la ruta, nunca el archivo en sí; el archivo vive en disco
    # dentro de la carpeta configurada en CARPETA_IMAGENES_PRODUCTOS. Es opcional:
    # un producto sin foto simplemente tiene este campo en None.
    imagen_url = Column(String(255), nullable=True)

    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))