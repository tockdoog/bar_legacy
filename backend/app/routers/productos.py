# Ruta: backend/app/routers/productos.py
# Endpoints para gestionar el inventario de productos: crear, listar, buscar
# por código de barras, actualizar, eliminar (desactivar), y subir/quitar
# la imagen de cada producto. Sistema de uso general (no depende de ningún
# nicho de negocio especifico). Precios y montos en pesos colombianos (COP).
#
# PERMISOS: consultar el inventario está disponible para cualquier empleado
# (necesario para operar el punto de venta). Crear, editar, eliminar y
# gestionar imágenes de productos requiere el permiso granular
# "inventario_gestionar" (el administrador siempre lo tiene por su rol; un
# empleado solo si el administrador se lo asignó desde Usuarios).

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol, requerir_permiso
from app.models.producto import Producto
from app.models.usuario import RolUsuario
from app.schemas.producto import ProductoCrear, ProductoActualizar, ProductoRespuesta
from app.utils.imagenes_productos import guardar_imagen_producto, eliminar_imagen_producto
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/productos", tags=["Inventario"])


@router.get("/", response_model=list[ProductoRespuesta])
def listar_productos(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista todos los productos activos del inventario."""
    return db.query(Producto).filter(Producto.activo.is_(True)).order_by(Producto.nombre).all()


@router.get("/inventario-bajo", response_model=list[ProductoRespuesta])
def listar_productos_inventario_bajo(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista los productos cuyo stock actual llegó o bajó del stock mínimo (para alertas del dashboard)."""
    return (
        db.query(Producto)
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .order_by(Producto.stock_actual)
        .all()
    )


@router.get("/buscar-por-codigo/{codigo_barras}", response_model=ProductoRespuesta)
def buscar_producto_por_codigo(
    codigo_barras: str,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Busca un producto mediante su código de barras (usado por el escáner)."""
    producto = db.query(Producto).filter(Producto.codigo_barras == codigo_barras).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto


# Límite de creación de productos: evita que una cuenta comprometida o un
# script automatizado registre cientos de productos falsos en segundos.
@router.post("/", response_model=ProductoRespuesta, status_code=status.HTTP_201_CREATED)
@limitador.limit("20/minute")
def crear_producto(
    request: Request,
    datos: ProductoCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("inventario_gestionar")),
):
    """
    Registra un nuevo producto en el inventario (sin imagen; esta se sube después
    con su propio endpoint).

    CORRECCIÓN DE CONSISTENCIA (código de barras + eliminación lógica):
    Los productos nunca se borran de la base de datos al "eliminarlos" desde el
    frontend; solo se marcan como activo=False (ver eliminar_producto más abajo).
    Antes, esta validación de duplicado buscaba el código de barras SIN filtrar
    por activo, mientras que el módulo de escáner (escaner/router.py) sí filtra
    por activo=True al decidir si un código "existe" o no. Esa diferencia
    causaba un caso confuso: el escáner reportaba el código como "no encontrado"
    (porque el único producto con ese código estaba inactivo), pero al intentar
    crear el producto nuevo, este endpoint SÍ encontraba el registro inactivo y
    lo rechazaba con 400 como si fuera un duplicado real.
    Ahora se distinguen dos casos:
      1) Ya existe un producto ACTIVO con ese código -> se rechaza (duplicado real).
      2) Existe un producto INACTIVO (eliminado antes) con ese código -> se
         reactiva y se sobrescriben sus datos con los nuevos, en vez de crear
         una fila nueva. Esto evita acumular productos "fantasma" duplicados
         en la tabla y mantiene coherente el historial de compras/ventas ya
         asociado a ese registro.
    """
    if datos.codigo_barras:
        producto_activo_existente = (
            db.query(Producto)
            .filter(
                Producto.codigo_barras == datos.codigo_barras,
                Producto.activo.is_(True),
            )
            .first()
        )
        if producto_activo_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un producto activo con ese código de barras",
            )

        producto_inactivo_existente = (
            db.query(Producto)
            .filter(
                Producto.codigo_barras == datos.codigo_barras,
                Producto.activo.is_(False),
            )
            .first()
        )
        if producto_inactivo_existente:
            # Reactiva el registro existente en lugar de crear uno nuevo,
            # actualizando todos sus campos con los datos recién enviados.
            for campo, valor in datos.model_dump().items():
                setattr(producto_inactivo_existente, campo, valor)
            producto_inactivo_existente.activo = True
            db.commit()
            db.refresh(producto_inactivo_existente)
            return producto_inactivo_existente

    nuevo_producto = Producto(**datos.model_dump())
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return nuevo_producto


@router.put("/{producto_id}", response_model=ProductoRespuesta)
def actualizar_producto(
    producto_id: int,
    datos: ProductoActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("inventario_gestionar")),
):
    """Actualiza parcialmente los datos de un producto existente."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    datos_actualizados = datos.model_dump(exclude_unset=True)

    # Si el código de barras se está modificando, valida que no choque con el
    # de OTRO producto ACTIVO ya existente (excluyendo el propio producto que
    # se está editando). Se filtra por activo=True por el mismo motivo que en
    # crear_producto: un producto desactivado no debería bloquear la reutilización
    # de su código de barras en otro producto activo.
    nuevo_codigo = datos_actualizados.get("codigo_barras")
    if nuevo_codigo:
        conflicto = (
            db.query(Producto)
            .filter(
                Producto.codigo_barras == nuevo_codigo,
                Producto.id != producto_id,
                Producto.activo.is_(True),
            )
            .first()
        )
        if conflicto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro producto activo con ese código de barras",
            )

    for campo, valor in datos_actualizados.items():
        setattr(producto, campo, valor)

    db.commit()
    db.refresh(producto)
    return producto


# Límite de subida de imágenes: procesar imágenes (Pillow) consume CPU;
# sin límite, una cuenta comprometida podría saturar el servidor subiendo
# archivos en bucle.
@router.post("/{producto_id}/imagen", response_model=ProductoRespuesta)
@limitador.limit("30/minute")
async def subir_imagen_producto(
    request: Request,
    producto_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("inventario_gestionar")),
):
    """
    Sube (o reemplaza) la imagen de un producto existente.
    El archivo se valida y se procesa en utils.imagenes_productos antes de
    guardarse: solo llegan a disco imágenes reales, ya redimensionadas.
    Si el producto ya tenía una imagen previa, el archivo anterior se elimina
    del disco para no acumular archivos huérfanos.
    """
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    imagen_anterior = producto.imagen_url
    nueva_ruta = await guardar_imagen_producto(archivo)

    producto.imagen_url = nueva_ruta
    db.commit()
    db.refresh(producto)

    if imagen_anterior:
        eliminar_imagen_producto(imagen_anterior)

    return producto


@router.delete("/{producto_id}/imagen", response_model=ProductoRespuesta)
def eliminar_imagen_de_producto(
    producto_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("inventario_gestionar")),
):
    """Quita la imagen de un producto (el producto queda sin foto, mostrando el ícono genérico en el frontend)."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    eliminar_imagen_producto(producto.imagen_url)
    producto.imagen_url = None
    db.commit()
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(
    producto_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("inventario_gestionar")),
):
    """Desactiva un producto (eliminación lógica, conserva el historial de ventas). La imagen no se borra."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    producto.activo = False
    db.commit()