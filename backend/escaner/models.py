# Ruta: backend/escaner/models.py
# Modelo de base de datos para registrar cada evento de escaneo de codigo de barras.
# Permite auditar el uso del escanador por modulo, usuario y resultado, y generar
# reportes de actividad sin depender de los logs del servidor (que se rotan y pierden).
# Separado de app/models/ para mantener el modulo de escanador autocontenido.
#
# CORRECCION DE ZONA HORARIA: "fecha" se guarda con ahora_colombia() (hora local
# de Colombia, sin zona), igual que ventas y compras. Antes usaba UTC, y el
# reporte de escaneos (que filtra con hora Colombia) podia ubicar un evento
# nocturno en otro dia.

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.zona_horaria import ahora_colombia


class EscaneoLog(Base):
    """
    Tabla que almacena cada evento de escaneo enviado por el frontend.
    Registra quien escaneo, que codigo, desde que modulo y si el producto
    fue encontrado en el inventario en ese momento.
    No almacena el codigo en claro sino un hash SHA-256 truncado para
    proteger informacion sensible del inventario en caso de acceso no autorizado.
    El codigo original se guarda solo cuando el producto fue encontrado,
    ya que en ese caso es un dato ya publico dentro del sistema.
    """
    __tablename__ = "escaneos_log"

    # Identificador unico autoincremental de cada evento de escaneo
    id = Column(Integer, primary_key=True, index=True)

    # Hash SHA-256 truncado del codigo escaneado (primeros 16 caracteres hex).
    codigo_hash = Column(String(16), nullable=False, index=True)

    # Codigo original: solo cuando el producto fue encontrado; NULL si no existia.
    codigo_barras = Column(String(64), nullable=True)

    # Modulo del frontend desde donde se lanzo el escaneo: "inventario", "pos" o "compras"
    modulo_origen = Column(String(30), nullable=False, default="desconocido")

    # Indica si el codigo escaneado coincidio con un producto activo del inventario
    encontrado = Column(Boolean, nullable=False, default=False)

    # Usuario autenticado que realizo el escaneo (se guarda el id, no el nombre)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    # Producto encontrado (NULL si el escaneo no encontro ninguno)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)

    # Marca de tiempo en hora LOCAL de Colombia (sin zona) del momento del escaneo
    fecha = Column(
        DateTime,
        nullable=False,
        default=ahora_colombia,
        index=True,
    )

    # Relaciones ORM para acceder al usuario y al producto sin JOIN manuales
    usuario = relationship("Usuario")
    producto = relationship("Producto")