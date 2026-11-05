# Ruta: backend/app/schemas/promocion.py
# Esquemas de validación de datos para las promociones (combos de productos).
#
# SEGURIDAD: los campos "costo_total", "ganancia_negocio" y
# "margen_ganancia_porcentaje" son opcionales (None por defecto) porque el
# backend (routers/promociones.py) solo los completa cuando quien consulta
# es ADMINISTRADOR. Un EMPLEADO recibe estos campos en null: el frontend
# nunca debe asumir que siempre vienen con valor.

from pydantic import BaseModel, Field


class ComponentePromocionCrear(BaseModel):
    """Un producto y su cantidad dentro de una promoción a crear."""
    producto_id: int
    cantidad: int = Field(gt=0)


class PromocionCrear(BaseModel):
    """Datos requeridos para crear una nueva promoción."""
    nombre: str = Field(min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)
    precio_promocional: float = Field(gt=0)
    items: list[ComponentePromocionCrear] = Field(min_length=1)


class PromocionActualizar(BaseModel):
    """Datos opcionales para editar una promoción existente."""
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    descripcion: str | None = None
    precio_promocional: float | None = Field(default=None, gt=0)
    activa: bool | None = None
    items: list[ComponentePromocionCrear] | None = None


class ComponentePromocionRespuesta(BaseModel):
    """
    Representa un producto componente dentro de la respuesta de una promoción.
    Incluye "imagen_url" (ruta relativa, ej: "/uploads/productos/xxx.jpg")
    para que el frontend pueda mostrar la foto de cada producto del combo
    sin tener que volver a consultar /api/productos/.
    """
    producto_id: int
    nombre_producto: str
    cantidad: int
    imagen_url: str | None = None

    model_config = {"from_attributes": True}


class PromocionRespuesta(BaseModel):
    """
    Representa una promoción completa.

    Campos SIEMPRE visibles (para ADMINISTRADOR y EMPLEADO):
      - valor_normal: suma de precios de venta normales de cada componente.
      - ahorro_cliente: cuánto se ahorra el cliente frente al valor normal.
      - porcentaje_descuento: ese ahorro expresado en porcentaje.

    Campos SOLO para ADMINISTRADOR (el router los deja en None si quien
    consulta es EMPLEADO, para no exponer información de costos/utilidad):
      - costo_total: suma de precios de COMPRA de cada componente.
      - ganancia_negocio: utilidad neta que deja la promoción al negocio.
      - margen_ganancia_porcentaje: esa utilidad expresada como % sobre el
        precio promocional de venta.
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