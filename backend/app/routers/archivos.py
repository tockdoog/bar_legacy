# Ruta: backend/app/routers/archivos.py
# Sirve las imágenes de los productos desde la base de datos. Si una imagen es
# antigua y aún está en disco (carpeta uploads/productos), se sirve desde allí.
# Es público a propósito: son fotos de catálogo cargadas con una etiqueta <img>,
# que no puede enviar el token. El nombre es un UUID imposible de adivinar y se
# valida con una expresión estricta (sin path traversal).

import os
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.config import configuracion
from app.database import obtener_db
from app.models.imagen_producto import ImagenProducto
from app.utils.rutas import ruta_absoluta

router = APIRouter(tags=["Archivos"])

PATRON_NOMBRE = re.compile(r"^[a-f0-9]{32}\.(jpg|png|webp)$")
MIME_POR_EXTENSION = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

# El nombre cambia cuando cambia la imagen, por eso puede cachearse un año
CABECERAS_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}


@router.get("/uploads/productos/{nombre}", include_in_schema=False)
def servir_imagen_producto(nombre: str, db: Session = Depends(obtener_db)):
    """Devuelve la imagen de un producto desde la base de datos (o desde disco si es antigua)."""
    if not PATRON_NOMBRE.match(nombre):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada")

    imagen = db.get(ImagenProducto, nombre)
    if imagen is not None:
        return Response(content=bytes(imagen.contenido), media_type=imagen.tipo_mime, headers=CABECERAS_CACHE)

    ruta = os.path.join(ruta_absoluta(configuracion.CARPETA_IMAGENES_PRODUCTOS), nombre)
    if os.path.isfile(ruta):
        extension = nombre.rsplit(".", 1)[-1]
        return FileResponse(ruta, media_type=MIME_POR_EXTENSION[extension], headers=CABECERAS_CACHE)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada")