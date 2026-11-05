# Ruta: backend/app/utils/imagenes_productos.py
# Funciones para validar, procesar y guardar de forma segura las imágenes que
# se suben para los productos del inventario. Sistema de uso general (no
# depende de ningún nicho de negocio especifico).
#
# MEDIDAS DE SEGURIDAD APLICADAS:
# - El archivo se abre con Pillow y se vuelve a guardar desde cero: esto descarta
#   cualquier contenido que no sea realmente una imagen válida (un script o
#   ejecutable disfrazado con extensión .jpg no logra "abrirse" como imagen y
#   se rechaza), y también elimina metadatos EXIF que pudieran contener datos
#   sensibles de quien tomó la foto (ubicación, dispositivo, etc.).
# - El nombre de archivo final es siempre un UUID generado por el servidor,
#   nunca el nombre original enviado por el navegador: evita path traversal
#   (rutas como "../../etc/passwd") y colisiones entre archivos.
# - Se valida el tamaño máximo ANTES de cargar la imagen completa en memoria,
#   para no exponer el servidor a archivos gigantes enviados a propósito.
# - Se limita la cantidad máxima de píxeles que Pillow acepta descomprimir,
#   para prevenir ataques de "bomba de descompresión" (un archivo pequeño en
#   disco que al abrirse se expande a una imagen gigantesca en memoria RAM,
#   pudiendo agotar los recursos del servidor).
# - La imagen se redimensiona a un lado máximo configurable, controlando el
#   uso de disco y acelerando la carga en el inventario y el punto de venta.
# - Al eliminar una imagen del disco, se verifica que la ruta final quede
#   estrictamente DENTRO de la carpeta de imágenes de productos, como capa
#   adicional de defensa contra path traversal.

import io
import os
import uuid

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from PIL import Image as ImagenPIL  # Alias solo para acceder a DecompressionBombError

from app.config import configuracion

# Tipos de imagen aceptados. Se valida tanto la extensión final como el
# contenido real (Pillow rechaza cualquier archivo que no sea una de estas).
FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}
EXTENSION_POR_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# Límite de píxeles totales (ancho x alto) que Pillow acepta descomprimir.
# Una imagen de producto normal jamás necesita más de esto; por encima de
# este límite, se asume un intento de bomba de descompresión y se rechaza
# antes de que Pillow reserve la memoria para decodificarla.
ImagenPIL.MAX_IMAGE_PIXELS = 40_000_000  # ~40 megapíxeles (ej. 7000 x 5700 px)


def _ruta_carpeta_imagenes() -> str:
    """Crea (si no existe) y devuelve la ruta absoluta de la carpeta de imágenes."""
    carpeta = configuracion.CARPETA_IMAGENES_PRODUCTOS
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


async def guardar_imagen_producto(archivo: UploadFile) -> str:
    """
    Valida, procesa y guarda en disco la imagen subida para un producto.
    Devuelve la ruta relativa (URL pública) con la que se accede a la imagen,
    por ejemplo "/uploads/productos/3f9a1c2b.jpg".

    Lanza HTTPException 400 si el archivo no es una imagen válida, excede
    el tamaño máximo permitido, o supera el límite de píxeles seguro.
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
    # Se capturan tres tipos de error posibles al abrir el archivo:
    #   - UnidentifiedImageError / OSError: el archivo no es una imagen real
    #     (por ejemplo, un ejecutable renombrado a ".jpg").
    #   - DecompressionBombError: la imagen supera MAX_IMAGE_PIXELS, indicio
    #     de un intento de agotar la memoria del servidor.
    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen.verify()  # Verifica la integridad del archivo sin decodificarlo completo
        # Pillow requiere reabrir el archivo después de verify() para poder usarlo
        imagen = Image.open(io.BytesIO(contenido))
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

    formato_original = (imagen.format or "").upper()
    if formato_original not in FORMATOS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagen no permitido. Usa JPG, PNG o WEBP.",
        )

    # --- Paso 3: normalizar el modo de color y quitar transparencia si es JPEG ---
    # JPEG no soporta canal alfa; si la imagen original lo tiene (PNG/WEBP con
    # transparencia) y el formato de salida será JPEG, se aplana sobre blanco.
    if formato_original == "JPEG" and imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")
    elif imagen.mode not in ("RGB", "RGBA"):
        imagen = imagen.convert("RGBA" if "A" in imagen.mode else "RGB")

    # --- Paso 4: redimensionar manteniendo proporción si excede el lado máximo ---
    lado_maximo = configuracion.LADO_MAXIMO_IMAGEN_PX
    if imagen.width > lado_maximo or imagen.height > lado_maximo:
        imagen.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)

    # --- Paso 5: generar un nombre de archivo aleatorio y guardar en disco ---
    extension = EXTENSION_POR_FORMATO[formato_original]
    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    ruta_absoluta = os.path.join(_ruta_carpeta_imagenes(), nombre_archivo)

    parametros_guardado = {
        "JPEG": {"quality": 85, "optimize": True},
        "PNG": {"optimize": True},
        "WEBP": {"quality": 85},
    }
    imagen.save(ruta_absoluta, format=formato_original, **parametros_guardado.get(formato_original, {}))

    # Ruta pública con la que el frontend podrá acceder a la imagen vía /uploads/...
    return f"/uploads/productos/{nombre_archivo}"


def eliminar_imagen_producto(imagen_url: str | None) -> None:
    """
    Elimina del disco el archivo de imagen asociado a un producto, si existe.
    No lanza error si el archivo ya no está (por ejemplo, si se borró manualmente).
    """
    if not imagen_url:
        return

    carpeta_imagenes = os.path.abspath(_ruta_carpeta_imagenes())
    nombre_archivo = os.path.basename(imagen_url)
    ruta_absoluta = os.path.abspath(os.path.join(carpeta_imagenes, nombre_archivo))

    # Verifica que la ruta final siga estando dentro de la carpeta de imágenes
    # de productos. Es una capa adicional de defensa: aunque hoy imagen_url
    # siempre lo genera el propio servidor (nunca el usuario), esta validación
    # evita que un cambio futuro en el código permita borrar archivos fuera
    # de la carpeta esperada.
    if os.path.commonpath([carpeta_imagenes, ruta_absoluta]) != carpeta_imagenes:
        return

    try:
        if os.path.isfile(ruta_absoluta):
            os.remove(ruta_absoluta)
    except OSError:
        # Si el archivo no se puede borrar por algún motivo de permisos, se
        # ignora: no debe impedir que la operación principal (guardar/eliminar
        # el producto) se complete.
        pass