# Ruta: backend/app/schemas/finanzas.py
# Esquemas de validacion de datos para el modulo de Analisis Financiero e
# Impuestos: configuracion de impuestos y margen, calculo de precio de venta
# recomendado, analisis de rentabilidad por producto y resumen financiero
# por periodo (ingresos, gastos, ganancia e impuestos estimados).

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.finanzas import TipoImpuesto


# --- Bloque: configuracion de impuestos y margen ---
class ConfiguracionFinancieraActualizar(BaseModel):
    """Datos para actualizar la configuracion financiera del negocio."""
    tipo_impuesto: TipoImpuesto
    porcentaje_impuesto: float = Field(ge=0, le=100)
    nombre_impuesto_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_deseado: float = Field(gt=0, le=95)
    margen_minimo_saludable: float = Field(ge=0, le=95)

    @model_validator(mode="after")
    def _validar_impuesto_personalizado(self) -> "ConfiguracionFinancieraActualizar":
        # Si se elige "personalizado", el nombre del impuesto es obligatorio
        # para poder mostrarlo identificado en reportes y en el frontend.
        if self.tipo_impuesto == TipoImpuesto.PERSONALIZADO and not (self.nombre_impuesto_personalizado or "").strip():
            raise ValueError("Debes indicar un nombre para el impuesto personalizado.")
        return self


class ConfiguracionFinancieraRespuesta(BaseModel):
    """Datos de la configuracion financiera devueltos al frontend."""
    tipo_impuesto: TipoImpuesto
    etiqueta_impuesto: str
    porcentaje_impuesto: float
    nombre_impuesto_personalizado: str | None
    margen_utilidad_deseado: float
    margen_minimo_saludable: float
    fecha_actualizacion: datetime | None = None

    model_config = {"from_attributes": True}


# --- Bloque: calculo de precio de venta recomendado ---
class CalculoPrecioSolicitud(BaseModel):
    """
    Datos para calcular el precio de venta recomendado a partir de un costo.
    Si "producto_id" se indica, el costo se toma del producto ya guardado en
    el inventario; si no, se usa "costo_compra" enviado directamente (util
    para simular productos que aun no existen en el sistema).
    """
    producto_id: int | None = None
    costo_compra: float | None = Field(default=None, ge=0)
    margen_utilidad_deseado: float | None = Field(default=None, gt=0, le=95)
    incluir_impuesto: bool = True

    @model_validator(mode="after")
    def _validar_origen_del_costo(self) -> "CalculoPrecioSolicitud":
        if self.producto_id is None and self.costo_compra is None:
            raise ValueError("Debes indicar un producto_id o un costo_compra.")
        return self


class CalculoPrecioRespuesta(BaseModel):
    """Desglose completo del calculo de precio de venta recomendado."""
    costo_compra: float
    margen_utilidad_aplicado: float
    utilidad_por_unidad: float
    precio_venta_sin_impuesto: float
    porcentaje_impuesto_aplicado: float
    valor_impuesto: float
    precio_venta_final: float
    margen_sobre_costo: float


# --- Bloque: analisis de rentabilidad por producto (recomendaciones) ---
class ProductoAnalisisFinanciero(BaseModel):
    """Analisis de rentabilidad de un producto ya existente en el inventario."""
    producto_id: int
    nombre: str
    precio_compra: float
    precio_venta_actual: float
    utilidad_actual_unitaria: float
    margen_actual_porcentaje: float
    precio_venta_recomendado: float
    estado: str  # "perdida" | "bajo_margen" | "saludable"
    mensaje: str


# --- Bloque: resumen financiero por periodo ---
class ResumenFinancieroRespuesta(BaseModel):
    """Panorama financiero del negocio en un rango de fechas."""
    fecha_inicio: datetime
    fecha_fin: datetime
    total_ingresos_ventas: float
    total_costo_ventas: float
    total_gastos_compras: float
    ganancia_bruta: float
    valor_impuesto_estimado_ventas: float
    ganancia_neta_estimada: float
    margen_promedio_real: float
    cantidad_ventas: int
    productos_en_perdida: int
    productos_bajo_margen: int