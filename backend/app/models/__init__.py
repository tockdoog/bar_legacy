# Ruta: backend/app/models/__init__.py
# Importa todos los modelos del paquete para que SQLAlchemy los registre siempre,
# sin depender de qué router se importe primero. Así Base.metadata.create_all()
# (ver main.py) crea todas las tablas en Neon y las relaciones entre modelos
# (por nombre) se resuelven de forma predecible.
# Los modelos de app/suscripcion/models.py y escaner/models.py se registran al
# importar sus routers desde main.py.

from app.models.finanzas import ConfiguracionFinanciera  # noqa: F401  (debe ir antes que venta y producto)
from app.models.usuario import Usuario  # noqa: F401
from app.models.categoria import Categoria  # noqa: F401
from app.models.producto import Producto  # noqa: F401
from app.models.imagen_producto import ImagenProducto  # noqa: F401
from app.models.mesa import Mesa  # noqa: F401
from app.models.bloqueo_mesa import BloqueoMesa  # noqa: F401
from app.models.proveedor import Proveedor  # noqa: F401
from app.models.compra import Compra, DetalleCompra  # noqa: F401
from app.models.promocion import Promocion, ComponentePromocion  # noqa: F401
from app.models.venta import Venta, DetalleVenta, PagoVentaDetalle  # noqa: F401
from app.models.registro_log import RegistroLog  # noqa: F401
from app.models.intento_login import IntentoLogin  # noqa: F401