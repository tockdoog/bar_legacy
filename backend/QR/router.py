# Ruta: backend/QR/router.py
# Endpoint que genera, directamente en el servidor, el código QR con la dirección
# del sistema para vincular un celular o tablet escaneándolo, en vez de escribir
# la dirección a mano. Solo el administrador puede usarlo.
#
# CAMBIO PARA VERCEL:
# - Producción (ENTORNO=produccion): el QR apunta al dominio del frontend, el primer
#   origen de CORS_ORIGINS (ej. https://tu-frontend.vercel.app). Ya no se usa IP_SERVIDOR.
# - Desarrollo (red local): se mantiene la lógica anterior con la IP local (IP_SERVIDOR),
#   porque los celulares no resuelven "barlegacy.local" sin configuración adicional.
#
# El QR se genera en memoria y nunca se guarda en disco.

import base64
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import configuracion
from app.dependencies import requerir_rol
from app.models.usuario import RolUsuario, Usuario
from app.utils.limitador import limitador
from QR.schemas import InformacionDispositivoQR

router = APIRouter(prefix="/api/qr", tags=["Vinculación de dispositivos"])


def _resolver_url_acceso() -> str:
    """Devuelve la dirección que debe abrir el dispositivo, según el entorno."""
    if configuracion.es_produccion:
        origenes = configuracion.lista_origenes_cors
        if not origenes:
            raise HTTPException(
                status_code=400,
                detail="No hay un dominio configurado. Define CORS_ORIGINS con la dirección del frontend.",
            )
        return origenes[0]

    if not configuracion.IP_SERVIDOR:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se detectó una IP de red para este servidor. Define IP_SERVIDOR "
                "(por ejemplo 192.168.0.14) en el archivo .env."
            ),
        )
    return f"https://{configuracion.IP_SERVIDOR}:5443"


@router.get("/dispositivo", response_model=InformacionDispositivoQR)
@limitador.limit("20/minute")  # Protege contra generación abusiva del QR
def obtener_qr_dispositivo(
    request: Request,
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
) -> InformacionDispositivoQR:
    """Genera el código QR con la dirección del sistema para vincular un nuevo dispositivo."""
    url_acceso = _resolver_url_acceso()

    # Bloque: genera la imagen del QR en memoria
    imagen_qr = qrcode.make(url_acceso, box_size=10, border=2)
    buffer_imagen = io.BytesIO()
    imagen_qr.save(buffer_imagen, format="PNG")

    # Bloque: la imagen viaja en base64 dentro de la misma respuesta (sin archivos en disco)
    imagen_base64 = base64.b64encode(buffer_imagen.getvalue()).decode("utf-8")

    return InformacionDispositivoQR(
        url_acceso=url_acceso,
        imagen_qr_base64=f"data:image/png;base64,{imagen_base64}",
    )