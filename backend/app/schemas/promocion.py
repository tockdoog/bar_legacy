# Ruta: backend/app/schemas/promocion.py
# Esquemas de validación de datos para las promociones (combos de productos). Precios en COP.
#
# SEGURIDAD: "costo_total", "ganancia_negocio" y "margen_ganancia_porcentaje" son opcionales
# (None por defecto) porque el router (routers/promociones.py) solo los completa cuando
# quien consulta es ADMINISTRADOR. Un EMPLEADO los recibe en null.
#
# CORRECCIONES (PostgreSQL/Neon, que sí hace cumplir los límites de las columnas):
# - "descripcion" tiene largo máximo también al editar.
# - Topes de precio, de cantidad por componente y de componentes por promoción.
# - Un null explícito en nombre, precio o estado se rechaza con 422 (antes daba error 500).

from pydantic import BaseModel, Field, field_validator, model_validator

PRECIO_MAXIMO_PROMOCION = 1_000_000_000  # Mil millones de pesos
CANTIDAD_MAXIMA_COMPONENTE = 1_000
MAXIMO_COMPONENTES = 30

# Campos de la promoción que en la base de datos no admiten nulo
CAMPOS_PROMOCION_NO_NULOS = ("nombre", "precio_promocional", "activa")


def _limpiar(valor):
    """Quita espacios de los bordes de un texto antes de validar su largo."""
    return valor.strip() if isinstance(valor, str) else valor


def _vacio_a_nulo(valor):
    """Convierte un texto vacío (o solo espacios) en None."""
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


class ComponentePromocionCrear(BaseModel):
    """Un producto y su cantidad dentro de una promoción a crear."""
    producto_id: int
    cantidad: int = Field(gt=0, le=CANTIDAD_MAXIMA_COMPONENTE)


class PromocionCrear(BaseModel):
    """Datos requeridos para crear una nueva promoción."""
    nombre: str = Field(min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)
    precio_promocional: float = Field(gt=0, le=PRECIO_MAXIMO_PROMOCION)
    items: list[ComponentePromocionCrear] = Field(min_length=1, max_length=MAXIMO_COMPONENTES)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("descripcion", mode="before")
    @classmethod
    def limpiar_descripcion(cls, valor):
        return _vacio_a_nulo(valor)


class PromocionActualizar(BaseModel):
    """Datos opcionales para editar una promoción existente."""
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)
    precio_promocional: float | None = Field(default=None, gt=0, le=PRECIO_MAXIMO_PROMOCION)
    activa: bool | None = None
    items: list[ComponentePromocionCrear] | None = Field(default=None, min_length=1, max_length=MAXIMO_COMPONENTES)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor):
        return _limpiar(valor)

    @field_validator("descripcion", mode="before")
    @classmethod
    def limpiar_descripcion(cls, valor):
        return _vacio_a_nulo(valor)

    @model_validator(mode="after")
    def _rechazar_nulos_explicitos(self) -> "PromocionActualizar":
        # Omitir un campo es válido (no se cambia); enviarlo como null en uno obligatorio no.
        for campo in CAMPOS_PROMOCION_NO_NULOS:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo.")
        return self


class ComponentePromocionRespuesta(BaseModel):
    """
    Producto componente dentro de la respuesta de una promoción. Incluye "imagen_url"
    (ruta relativa, ej: "/uploads/productos/xxx.jpg") para mostrar la foto de cada
    producto del combo sin volver a consultar /api/productos/.
    """
    producto_id: int
    nombre_producto: str
    cantidad: int
    imagen_url: str | None = None

    model_config = {"from_attributes": True}


class PromocionRespuesta(BaseModel):
    """
    Promoción completa.

    Campos SIEMPRE visibles (ADMINISTRADOR y EMPLEADO):
      - valor_normal: suma de precios de venta normales de cada componente.
      - ahorro_cliente: cuánto se ahorra el cliente frente al valor normal.
      - porcentaje_descuento: ese ahorro expresado en porcentaje.

    Campos SOLO para ADMINISTRADOR (el router los deja en None para el EMPLEADO):
      - costo_total: suma de precios de COMPRA de cada componente.
      - ganancia_negocio: utilidad neta que deja la promoción al negocio.
      - margen_ganancia_porcentaje: esa utilidad como % del precio promocional.
    """
    id: int
    nombre: str
    descripcion: str | None
    precio_promocional: float
    valor_normal: float
    ahorro_cliente: float
    porcentaje_descuento: float
    activa: bool
    componentes: list[ComponentePromocionRespuesta] = []

    # --- Datos financieros sensibles: solo para ADMINISTRADOR ---
    costo_total: float | None = None
    ganancia_negocio: float | None = None
    margen_ganancia_porcentaje: float | None = None

    model_config = {"from_attributes": True}