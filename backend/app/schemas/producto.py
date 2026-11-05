# Ruta: backend/app/schemas/producto.py
# Esquemas de validación de datos para crear, actualizar y mostrar productos del inventario.
# Incluye la configuración propia de impuesto y margen (Análisis Financiero),
# usada solo cuando el producto NO usa la configuración global del negocio.

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.finanzas import TipoImpuesto


class ProductoBase(BaseModel):
    """Campos comunes del producto. Sin reglas de negocio: estos campos los usan
    tanto los esquemas de entrada como el de salida, así que aquí solo van
    validaciones de formato (longitudes, mínimos), nunca reglas que dependan
    de datos ya guardados."""
    nombre: str = Field(min_length=2, max_length=120)
    codigo_barras: str | None = Field(default=None, max_length=64)
    categoria_id: int | None = None
    presentacion: str = Field(default="unidad", max_length=60)
    precio_compra: float = Field(ge=0)
    precio_venta: float = Field(ge=0)
    stock_actual: int = Field(ge=0, default=0)
    stock_minimo: int = Field(ge=0, default=0)

    # --- Configuración propia de impuesto y margen (Análisis Financiero) ---
    # "usar_configuracion_global=True" (por defecto) ignora los 4 campos de
    # abajo: el producto siempre hereda el impuesto y margen configurados en
    # el módulo de Análisis Financiero. Se pasa a False solo para productos
    # que necesitan un impuesto o margen distinto al resto del negocio
    # (ej: un producto exento mientras el resto cobra IVA).
    usar_configuracion_global: bool = True
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = Field(default=None, ge=0, le=100)
    nombre_impuesto_propio_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_propio: float | None = Field(default=None, gt=0, le=95)

    @model_validator(mode="after")
    def _validar_configuracion_propia(self) -> "ProductoBase":
        # Si el producto NO usa la configuración global, exige al menos el
        # tipo de impuesto propio (el porcentaje puede quedar en 0 si el
        # tipo es "sin_impuesto"), y el nombre personalizado si aplica.
        if not self.usar_configuracion_global:
            if self.tipo_impuesto_propio is None:
                raise ValueError(
                    "Si el producto no usa la configuración global, debes indicar su tipo de impuesto propio."
                )
            if self.tipo_impuesto_propio == TipoImpuesto.PERSONALIZADO and not (
                self.nombre_impuesto_propio_personalizado or ""
            ).strip():
                raise ValueError("Debes indicar un nombre para el impuesto personalizado del producto.")
        return self


class ProductoCrear(ProductoBase):
    """
    Datos requeridos para registrar un nuevo producto en el inventario.
    La regla de negocio (precio de venta >= precio de compra) vive aquí,
    porque solo debe aplicar a datos que el usuario está enviando en ese momento.
    No debe heredarse en ProductoRespuesta: un registro histórico ya guardado
    no debe romper el listado completo solo porque no cumple una regla actual.

    No incluye imagen_url: la imagen se sube por separado, mediante el endpoint
    POST /api/productos/{id}/imagen, una vez que el producto ya tiene un id.
    """

    @field_validator("precio_venta")
    @classmethod
    def precio_venta_coherente(cls, valor: float, info) -> float:
        # Regla de negocio: el precio de venta no debería ser menor al de compra
        precio_compra = info.data.get("precio_compra")
        if precio_compra is not None and valor < precio_compra:
            raise ValueError("El precio de venta no puede ser menor al precio de compra")
        return valor


class ProductoActualizar(BaseModel):
    """Datos opcionales para actualizar parcialmente un producto existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    codigo_barras: str | None = None
    categoria_id: int | None = None
    presentacion: str | None = None
    precio_compra: float | None = Field(default=None, ge=0)
    precio_venta: float | None = Field(default=None, ge=0)
    stock_actual: int | None = Field(default=None, ge=0)
    stock_minimo: int | None = Field(default=None, ge=0)
    activo: bool | None = None

    usar_configuracion_global: bool | None = None
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = Field(default=None, ge=0, le=100)
    nombre_impuesto_propio_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_propio: float | None = Field(default=None, gt=0, le=95)

    @field_validator("precio_venta")
    @classmethod
    def precio_venta_coherente(cls, valor: float | None, info) -> float | None:
        # Solo se valida si en la misma petición llegan ambos precios juntos.
        # Si solo llega uno de los dos, no hay forma de comparar aquí contra el
        # valor que ya está guardado en la base de datos (eso quedaría a cargo
        # del router si se necesita en el futuro).
        if valor is None:
            return valor
        precio_compra = info.data.get("precio_compra")
        if precio_compra is not None and valor < precio_compra:
            raise ValueError("El precio de venta no puede ser menor al precio de compra")
        return valor

    @model_validator(mode="after")
    def _validar_configuracion_propia(self) -> "ProductoActualizar":
        # Solo valida si esta petición está explícitamente desactivando la
        # configuración global; si no toca ese campo, no hay nada que exigir.
        if self.usar_configuracion_global is False and self.tipo_impuesto_propio is None:
            raise ValueError(
                "Si desactivas la configuración global, debes indicar el tipo de impuesto propio."
            )
        if (
            self.tipo_impuesto_propio == TipoImpuesto.PERSONALIZADO
            and not (self.nombre_impuesto_propio_personalizado or "").strip()
        ):
            raise ValueError("Debes indicar un nombre para el impuesto personalizado del producto.")
        return self


class ProductoRespuesta(ProductoBase):
    """
    Datos del producto que se devuelven al frontend.
    A propósito NO hereda de ProductoCrear ni repite su validador: los datos que
    ya están guardados deben poder mostrarse siempre, incluso si un registro
    antiguo no cumple una regla de negocio actual. Validar reglas de negocio en
    la salida de datos rompe toda la API con un solo registro inconsistente.
    """
    id: int
    activo: bool
    imagen_url: str | None = None

    model_config = {"from_attributes": True}