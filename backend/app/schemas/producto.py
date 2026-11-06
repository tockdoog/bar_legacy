# Ruta: backend/app/schemas/producto.py
# Esquemas de validación para crear, actualizar y mostrar productos del inventario.
# Incluye la configuración propia de impuesto y margen (Análisis Financiero), usada
# solo cuando el producto NO usa la configuración global del negocio. Precios en COP.
#
# SEGURIDAD: ProductoRespuesta declara "precio_compra" y la configuración propia como
# opcionales; el router los entrega en None a quien no puede ver costos (ver
# routers/productos.py), para que un empleado no conozca el margen de utilidad.
#
# CORRECCIONES (PostgreSQL/Neon, que a diferencia de SQLite sí hace cumplir los límites):
# - Largo máximo del código de barras y la presentación también al ACTUALIZAR.
# - Topes de precio y de stock (evitan desbordar la columna entera).
# - Un código de barras vacío o de solo espacios se guarda como nulo (la columna es
#   única: dos productos con "" chocarían).
# - Un null explícito en un campo obligatorio se rechaza con 422 (antes daba error 500).

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.finanzas import TipoImpuesto

PRECIO_MAXIMO = 1_000_000_000  # Mil millones de pesos
STOCK_MAXIMO = 1_000_000

# Campos que en la base de datos no admiten nulo
CAMPOS_NO_NULOS = (
    "nombre",
    "presentacion",
    "precio_compra",
    "precio_venta",
    "stock_actual",
    "stock_minimo",
    "activo",
    "usar_configuracion_global",
)


def _limpiar_codigo_barras(valor: str | None) -> str | None:
    """Quita espacios del código de barras; si queda vacío, lo convierte en nulo."""
    if valor is None:
        return None
    return valor.strip() or None


class ProductoBase(BaseModel):
    """Campos comunes de entrada del producto: solo validaciones de formato."""
    nombre: str = Field(min_length=2, max_length=120)
    codigo_barras: str | None = Field(default=None, max_length=64)
    categoria_id: int | None = None
    presentacion: str = Field(default="unidad", min_length=1, max_length=60)
    precio_compra: float = Field(ge=0, le=PRECIO_MAXIMO)
    precio_venta: float = Field(ge=0, le=PRECIO_MAXIMO)
    stock_actual: int = Field(ge=0, le=STOCK_MAXIMO, default=0)
    stock_minimo: int = Field(ge=0, le=STOCK_MAXIMO, default=0)

    # "usar_configuracion_global=True" ignora los 4 campos de abajo: el producto
    # hereda el impuesto y margen del módulo de Análisis Financiero.
    usar_configuracion_global: bool = True
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = Field(default=None, ge=0, le=100)
    nombre_impuesto_propio_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_propio: float | None = Field(default=None, gt=0, le=95)

    @field_validator("codigo_barras")
    @classmethod
    def _normalizar_codigo(cls, valor: str | None) -> str | None:
        return _limpiar_codigo_barras(valor)

    @model_validator(mode="after")
    def _validar_configuracion_propia(self) -> "ProductoBase":
        # Si el producto NO usa la configuración global, exige su tipo de impuesto propio
        # y, si es personalizado, su nombre.
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
    Datos para registrar un nuevo producto. La regla de negocio (precio de venta >= precio
    de compra) vive aquí porque solo aplica a datos que el usuario envía en ese momento,
    no a registros históricos. La imagen se sube aparte: POST /api/productos/{id}/imagen.
    """

    @field_validator("precio_venta")
    @classmethod
    def precio_venta_coherente(cls, valor: float, info) -> float:
        precio_compra = info.data.get("precio_compra")
        if precio_compra is not None and valor < precio_compra:
            raise ValueError("El precio de venta no puede ser menor al precio de compra")
        return valor


class ProductoActualizar(BaseModel):
    """Datos opcionales para actualizar parcialmente un producto existente."""
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    codigo_barras: str | None = Field(default=None, max_length=64)
    categoria_id: int | None = None
    presentacion: str | None = Field(default=None, min_length=1, max_length=60)
    precio_compra: float | None = Field(default=None, ge=0, le=PRECIO_MAXIMO)
    precio_venta: float | None = Field(default=None, ge=0, le=PRECIO_MAXIMO)
    stock_actual: int | None = Field(default=None, ge=0, le=STOCK_MAXIMO)
    stock_minimo: int | None = Field(default=None, ge=0, le=STOCK_MAXIMO)
    activo: bool | None = None

    usar_configuracion_global: bool | None = None
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = Field(default=None, ge=0, le=100)
    nombre_impuesto_propio_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_propio: float | None = Field(default=None, gt=0, le=95)

    @field_validator("codigo_barras")
    @classmethod
    def _normalizar_codigo(cls, valor: str | None) -> str | None:
        return _limpiar_codigo_barras(valor)

    @field_validator("precio_venta")
    @classmethod
    def precio_venta_coherente(cls, valor: float | None, info) -> float | None:
        # Solo se compara si en la misma petición llegan ambos precios.
        if valor is None:
            return valor
        precio_compra = info.data.get("precio_compra")
        if precio_compra is not None and valor < precio_compra:
            raise ValueError("El precio de venta no puede ser menor al precio de compra")
        return valor

    @model_validator(mode="after")
    def _rechazar_nulos_explicitos(self) -> "ProductoActualizar":
        # Omitir un campo es válido (no se cambia); enviarlo como null en uno obligatorio no.
        for campo in CAMPOS_NO_NULOS:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo.")
        return self

    @model_validator(mode="after")
    def _validar_configuracion_propia(self) -> "ProductoActualizar":
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


class ProductoRespuesta(BaseModel):
    """
    Datos del producto que se devuelven al frontend. Sin reglas de negocio: un registro
    antiguo que no cumpla una regla actual debe poder mostrarse. "precio_compra" y la
    configuración propia son opcionales porque el router los entrega en None a los
    usuarios sin permiso de gestionar el inventario (datos financieros sensibles).
    """
    id: int
    nombre: str
    codigo_barras: str | None = None
    categoria_id: int | None = None
    presentacion: str
    precio_compra: float | None = None
    precio_venta: float
    stock_actual: int
    stock_minimo: int
    usar_configuracion_global: bool = True
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = None
    nombre_impuesto_propio_personalizado: str | None = None
    margen_utilidad_propio: float | None = None
    activo: bool
    imagen_url: str | None = None

    model_config = {"from_attributes": True}