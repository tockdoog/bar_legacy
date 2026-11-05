# Ruta: backend/escaner/schemas.py
# Esquemas Pydantic para las respuestas del módulo de escáner de códigos de barras.
# Se mantienen separados de app/schemas/producto.py para no acoplar el módulo
# de escáner con la lógica interna del inventario.

from pydantic import BaseModel


class ResultadoEscaneo(BaseModel):
    """
    Respuesta devuelta al frontend cuando se busca un producto por código de barras.
    Incluye solo los campos relevantes para decidir la acción (agregar al carrito
    o pre-rellenar el formulario de inventario), sin exponer datos internos del ORM.
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
    Permite detectar intentos repetidos de códigos inexistentes (posible inventario
    desactualizado o intento de manipulación) sin guardar datos sensibles del cliente.
    """

    codigo_escaneado: str  # Valor leído por el escáner (nunca se guarda completo en logs)
    origen: str  # "inventario" | "pos" | "compras" – módulo desde donde se escaneó
    encontrado: bool  # Si el código existía en el momento del escaneo