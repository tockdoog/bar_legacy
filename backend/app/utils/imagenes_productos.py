# Ruta: backend/app/utils/imagenes_productos.py
# Valida, procesa y guarda de forma segura las imágenes de los productos.
# Precios y negocio no dependen de ningún nicho.
#
# CAMBIO: la imagen procesada se guarda en la base de datos (tabla
# imagenes_producto) y no en disco, porque el disco de Vercel es de solo
# lectura. La URL pública sigue siendo "/uploads/productos/<uuid>.<ext>".
#
# MEDIDAS DE SEGURIDAD (sin cambios):
# - Pillow abre y vuelve a guardar la imagen: descarta archivos disfrazados y
#   elimina metadatos EXIF.
# - El nombre final es un UUID generado por el servidor (sin path traversal).
# - Se valida el tamaño antes de procesar y se limita el número de píxeles
#   (protección contra bombas de descompresión).
# - Se redimensiona a un lado máximo configurable.

import io
import os
import re
import uuid

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from PIL import Image as ImagenPIL

from app.config import configuracion
from app.database import SesionLocal
from app.models.imagen_producto import ImagenProducto
from app.utils.rutas import ruta_absoluta

FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}
EXTENSION_POR_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
MIME_POR_FORMATO = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
PATRON_NOMBRE_ARCHIVO = re.compile(r"^[a-f0-9]{32}\.(jpg|png|webp)$")

# Límite de píxeles que Pillow acepta descomprimir (~40 megapíxeles)
ImagenPIL.MAX_IMAGE_PIXELS = 40_000_000


async def guardar_imagen_producto(archivo: UploadFile) -> str:
    """
    Valida, procesa y guarda en la base de datos la imagen subida para un producto.
    Devuelve la URL pública, por ejemplo "/uploads/productos/3f9a1c2b....jpg".
    Lanza HTTPException 400 si no es una imagen válida o excede los límites.
    """
    # --- Paso 1: leer el contenido y validar el tamaño antes de procesarlo ---
    contenido = await archivo.read()
    if len(contenido) > configuracion.TAMANO_MAXIMO_IMAGEN_BYTES:
        limite_mb = configuracion.TAMANO_MAXIMO_IMAGEN_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La imagen no puede superar los {limite_mb:.0f} MB.",
        )
    if len(contenido) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")

    # --- Paso 2: abrir con Pillow para confirmar que es una imagen real ---
    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen.verify()
        imagen = Image.open(io.BytesIO(contenido))  # verify() obliga a reabrir
        imagen.load()
    except ImagenPIL.DecompressionBombError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen es demasiado grande en resolución. Usa una foto de menor tamaño.",
        )
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una imagen válida (formatos permitidos: JPG, PNG, WEBP).",
        )

    formato = (imagen.format or "").upper()
    if formato not in FORMATOS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagen no permitido. Usa JPG, PNG o WEBP.",
        )

    # --- Paso 3: normalizar el modo de color (JPEG no admite canal alfa) ---
    if formato == "JPEG" and imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")
    elif imagen.mode not in ("RGB", "RGBA"):
        imagen = imagen.convert("RGBA" if "A" in imagen.mode else "RGB")

    # --- Paso 4: redimensionar manteniendo proporción ---
    lado_maximo = configuracion.LADO_MAXIMO_IMAGEN_PX
    if imagen.width > lado_maximo or imagen.height > lado_maximo:
        imagen.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)

    # --- Paso 5: re-codificar en memoria y guardar en la base de datos ---
    parametros = {
        "JPEG": {"quality": 85, "optimize": True},
        "PNG": {"optimize": True},
        "WEBP": {"quality": 85},
    }
    salida = io.BytesIO()
    imagen.save(salida, format=formato, **parametros.get(formato, {}))

    nombre_archivo = f"{uuid.uuid4().hex}{EXTENSION_POR_FORMATO[formato]}"
    db = SesionLocal()
    try:
        db.add(
            ImagenProducto(
                nombre=nombre_archivo,
                tipo_mime=MIME_POR_FORMATO[formato],
                contenido=salida.getvalue(),
            )
        )
        db.commit()
    finally:
        db.close()

    return f"/uploads/productos/{nombre_archivo}"


def eliminar_imagen_producto(imagen_url: str | None) -> None:
    """
    Elimina la imagen de un producto: la fila de la base de datos y, si existiera,
    un archivo antiguo en disco (imágenes subidas antes de este cambio). Nunca
    lanza error: no debe impedir la operación principal.
    """
    if not imagen_url:
        return

    nombre_archivo = os.path.basename(imagen_url)
    # Solo se aceptan nombres generados por el servidor (evita path traversal)
    if not PATRON_NOMBRE_ARCHIVO.match(nombre_archivo):
        return

    db = SesionLocal()
    try:
        db.query(ImagenProducto).filter(ImagenProducto.nombre == nombre_archivo).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Archivo antiguo en disco (solo local): se borra si existe y es posible
    ruta = os.path.join(ruta_absoluta(configuracion.CARPETA_IMAGENES_PRODUCTOS), nombre_archivo)
    try:
        if os.path.isfile(ruta):
            os.remove(ruta)
    except OSError:
        pass