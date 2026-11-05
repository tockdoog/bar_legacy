# Ruta: backend/app/schemas/producto.py
# Esquemas de validación de datos para crear, actualizar y mostrar productos del inventario.
# Incluye la configuración propia de impuesto y margen (Análisis Financiero),
# usada solo cuando el producto NO usa la configuración global del negocio.
#
# CAMBIO DE SEGURIDAD: ProductoRespuesta ya no hereda de ProductoBase y declara
# "precio_compra" y los campos de configuración propia como opcionales. El router
# los devuelve en None a quien no puede ver costos (ver routers/productos.py),
# evitando que un empleado conozca el margen de utilidad del negocio.

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.finanzas import TipoImpuesto


class ProductoBase(BaseModel):
    """Campos comunes de entrada del producto: solo validaciones de formato."""
    nombre: str = Field(min_length=2, max_length=120)
    codigo_barras: str | None = Field(default=None, max_length=64)
    categoria_id: int | None = None
    presentacion: str = Field(default="unidad", max_length=60)
    precio_compra: float = Field(ge=0)
    precio_venta: float = Field(ge=0)
    stock_actual: int = Field(ge=0, default=0)
    stock_minimo: int = Field(ge=0, default=0)

    # "usar_configuracion_global=True" ignora los 4 campos de abajo: el producto
    # hereda el impuesto y margen del módulo de Análisis Financiero.
    usar_configuracion_global: bool = True
    tipo_impuesto_propio: TipoImpuesto | None = None
    porcentaje_impuesto_propio: float | None = Field(default=None, ge=0, le=100)
    nombre_impuesto_propio_personalizado: str | None = Field(default=None, max_length=80)
    margen_utilidad_propio: float | None = Field(default=None, gt=0, le=95)

    @model_validator(mode="after")
    def _validar_configuracion_propia(self) -> "ProductoBase":
        # Si el producto NO usa la configuración global, exige el tipo de
        # impuesto propio y, si es personalizado, su nombre.
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
    Datos requeridos para registrar un nuevo producto. La regla de negocio
    (precio de venta >= precio de compra) vive aquí porque solo aplica a datos
    que el usuario envía en ese momento, no a registros históricos.
    La imagen se sube aparte: POST /api/productos/{id}/imagen.
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
        # Solo se compara si en la misma petición llegan ambos precios.
        if valor is None:
            return valor
        precio_compra = info.data.get("precio_compra")
        if precio_compra is not None and valor < precio_compra:
            raise ValueError("El precio de venta no puede ser menor al precio de compra")
        return valor

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
    Datos del producto que se devuelven al frontend. Sin reglas de negocio:
    un registro antiguo que no cumpla una regla actual debe poder mostrarse.

    "precio_compra" y los campos de configuración propia son opcionales
    porque el router los entrega en None a los usuarios sin permiso de
    gestionar el inventario (datos financieros sensibles).
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