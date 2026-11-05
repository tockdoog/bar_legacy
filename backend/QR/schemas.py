# Ruta: backend/QR/schemas.py
# Esquema de respuesta del endpoint que genera el código QR para vincular un
# nuevo dispositivo (celular o tablet) al sistema. Se mantiene en su propio
# módulo (backend/QR/) porque no representa un recurso de negocio: es una
# utilidad de conexión, no debe mezclarse con app/schemas/*.

from pydantic import BaseModel


class InformacionDispositivoQR(BaseModel):
    """
    Respuesta devuelta al frontend con la dirección de acceso del sistema
    en la red local (IP del servidor, pensada para celulares) y su
    representación como código QR, lista para mostrarse directamente en
    una etiqueta <img> (formato "data URL" en base64).
    """

    url_acceso: str  # Ej: "https://192.168.0.14:5443"
    imagen_qr_base64: str  # Ej: "data:image/png;base64,iVBORw0KG..."