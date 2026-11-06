# Ruta: backend/app/models/imagen_producto.py
# Guarda en la base de datos las imágenes ya procesadas de los productos. Se usa
# la base (Neon) y no el disco porque el disco de Vercel es de solo lectura y
# se pierde entre invocaciones. Cada imagen pesa unos cientos de KB como máximo
# (se redimensiona a 800 px), así que cabe de sobra en el plan gratuito.

from sqlalchemy import Column, DateTime, LargeBinary, String

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class ImagenProducto(Base):
    """Imagen de un producto; "nombre" es el archivo público (uuid + extensión)."""
    __tablename__ = "imagenes_producto"

    nombre = Column(String(80), primary_key=True)
    tipo_mime = Column(String(30), nullable=False)
    contenido = Column(LargeBinary, nullable=False)
    fecha = Column(DateTime, default=ahora_colombia)