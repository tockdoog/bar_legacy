# Ruta: backend/QR/router.py
# Endpoint que genera, bajo demanda y directamente en el servidor (sin
# depender de ninguna API externa ni de conexión a internet), el código QR
# con la dirección HTTPS del sistema en la red local. Permite que un
# administrador vincule un nuevo celular o tablet escaneando el código en
# vez de escribir la dirección a mano. Solo el rol administrador puede
# acceder, porque expone la dirección de red interna del negocio.
#
# IMPORTANTE: el QR usa la IP local del servidor (IP_SERVIDOR) y NO el
# hostname fijo (NOMBRE_HOST/"barlegacy.local"). Esto es intencional: los
# celulares (Android/iOS) no pueden resolver ese hostname sin instalar una
# app externa para editar su archivo hosts, mientras que una dirección IP
# funciona de inmediato al escanearla, sin ninguna configuración adicional
# en el dispositivo. Las computadoras, en cambio, siguen usando el
# hostname fijo (ver execution/windows/instalar.bat, que lo agrega al
# archivo hosts de la máquina donde corre el instalador).

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


@router.get("/dispositivo", response_model=InformacionDispositivoQR)
@limitador.limit("20/minute")  # Protege contra generación abusiva del QR
def obtener_qr_dispositivo(
    request: Request,
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
) -> InformacionDispositivoQR:
    """
    Genera el código QR con la URL HTTPS del sistema apuntando a la IP local
    del servidor, para que un celular lo escanee y abra el sistema sin
    escribir la dirección a mano ni necesitar configuración de red previa.
    """
    # --- Bloque: valida que la IP del servidor esté configurada ---
    # IP_SERVIDOR se detecta automáticamente en la instalación (ver
    # execution/windows/instalar.bat) y se inyecta vía docker-compose. Si
    # llegara vacía (ej. no se pudo detectar la red, o se corrió el backend
    # fuera del instalador oficial), se informa el problema con claridad en
    # vez de generar un QR con una URL rota.
    if not configuracion.IP_SERVIDOR:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se detectó una IP de red para este servidor. Vuelve a "
                "ejecutar el instalador para detectarla automáticamente, o "
                "define IP_SERVIDOR manualmente en docker/.env."
            ),
        )

    # --- Bloque: arma la URL de acceso a partir de la IP local del servidor ---
    url_acceso = f"https://{configuracion.IP_SERVIDOR}:5443"

    # --- Bloque: genera la imagen del QR en memoria (nunca se guarda en disco,
    # así no queda ningún archivo con datos de red del negocio en el servidor) ---
    imagen_qr = qrcode.make(url_acceso, box_size=10, border=2)
    buffer_imagen = io.BytesIO()
    imagen_qr.save(buffer_imagen, format="PNG")

    # --- Bloque: codifica la imagen como base64 para enviarla directamente
    # al frontend en la misma respuesta, sin necesidad de un endpoint de
    # archivo estático aparte ni de guardar nada en disco ---
    imagen_base64 = base64.b64encode(buffer_imagen.getvalue()).decode("utf-8")

    return InformacionDispositivoQR(
        url_acceso=url_acceso,
        imagen_qr_base64=f"data:image/png;base64,{imagen_base64}",
    )