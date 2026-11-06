# Ruta: backend/escaner/schemas.py
# Esquemas Pydantic del módulo de escáner de códigos de barras. Se mantienen separados
# de app/schemas/producto.py para no acoplar el escáner con la lógica del inventario.
#
# CORRECCIÓN: el código escaneado y el origen tienen largo máximo (64 y 30), igual que
# las columnas de la tabla escaneos_log, que PostgreSQL sí hace cumplir.

from pydantic import BaseModel, Field


class ResultadoEscaneo(BaseModel):
    """
    Respuesta al buscar un producto por código de barras. Incluye solo los campos
    relevantes para decidir la acción (agregar al carrito o pre-rellenar el formulario
    de inventario), sin exponer datos internos del ORM. "precio_compra" solo llega a
    quien puede ver costos.
    """

    encontrado: bool  # True si existe un producto activo con ese código

    # Campos presentes solo cuando encontrado=True
    id: int | None = None
    nombre: str | None = None
    codigo_barras: str | None = None
    precio_venta: float | None = None
    precio_compra: float | None = None
    stock_actual: int | None = None
    stock_minimo: int | None = None
    presentacion: str | None = None
    categoria_id: int | None = None
    imagen_url: str | None = None

    model_config = {"from_attributes": True}


class RegistroEscaneoBitacora(BaseModel):
    """
    Registro de auditoría enviado por el frontend cada vez que se escanea un código.
    Permite detectar intentos repetidos de códigos inexistentes (inventario desactualizado
    o intento de manipulación) sin guardar datos sensibles del cliente.
    """

    codigo_escaneado: str = Field(min_length=1, max_length=64)  # Nunca se guarda completo en logs
    origen: str = Field(min_length=1, max_length=30)  # "inventario" | "pos" | "compras"
    encontrado: bool  # Si el código existía en el momento del escaneo