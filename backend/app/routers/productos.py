# Ruta: backend/app/routers/productos.py
# Endpoints para gestionar el inventario de productos: crear, listar, buscar por código de
# barras, actualizar, eliminar (desactivar) y subir/quitar la imagen de cada producto.
# Precios y montos en pesos colombianos (COP).
#
# PERMISOS: consultar el inventario está disponible para cualquier empleado (necesario para
# operar el punto de venta). Crear, editar, eliminar y gestionar imágenes requiere el permiso
# granular "inventario_gestionar".
#
# SEGURIDAD (datos financieros): el costo de compra y la configuración propia de impuesto y
# margen revelan la utilidad del negocio. Solo se entregan a quien tiene "inventario_gestionar"
# (o es administrador); para los demás salen en None. Ver _a_respuesta().
#
# TRAZABILIDAD: los cambios de precio y existencias, las eliminaciones y las reactivaciones
# se registran en el log de negocio con el valor anterior y el nuevo.
#
# CORRECCIONES (PostgreSQL/Neon):
# - El código de barras es único entre TODOS los productos, incluidos los eliminados: al
#   editar, un código de un producto eliminado ahora responde 400 con un mensaje claro
#   (antes la restricción única fallaba con error 500).
# - Una categoría inexistente responde 404 (antes violaba la llave foránea y daba 500).
# - Dos solicitudes simultáneas con el mismo código responden 400 en vez de 500.
# - Buscar por código solo devuelve productos ACTIVOS.

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol, requerir_permiso
from app.logs.logger import registrar_negocio
from app.models.categoria import Categoria
from app.models.producto import Producto
from app.models.usuario import RolUsuario, Usuario
from app.schemas.producto import ProductoCrear, ProductoActualizar, ProductoRespuesta
from app.utils.imagenes_productos import guardar_imagen_producto, eliminar_imagen_producto
from app.utils.limitador import limitador

router = APIRouter(prefix="/api/productos", tags=["Inventario"])

# Campos cuyo cambio se deja registrado en el log de negocio
_CAMPOS_AUDITADOS = ("precio_venta", "precio_compra", "stock_actual")


def _puede_ver_costos(usuario: Usuario) -> bool:
    """El administrador y quien gestiona el inventario pueden ver costos y márgenes."""
    return usuario.rol == RolUsuario.ADMINISTRADOR or "inventario_gestionar" in usuario.permisos_lista


def _a_respuesta(producto: Producto, usuario: Usuario) -> ProductoRespuesta:
    """Convierte un producto en su respuesta, ocultando los datos de costo a quien no corresponde."""
    respuesta = ProductoRespuesta.model_validate(producto)
    if _puede_ver_costos(usuario):
        return respuesta
    return respuesta.model_copy(
        update={
            "precio_compra": None,
            "tipo_impuesto_propio": None,
            "porcentaje_impuesto_propio": None,
            "nombre_impuesto_propio_personalizado": None,
            "margen_utilidad_propio": None,
        }
    )


def _validar_categoria(db: Session, categoria_id: int | None) -> None:
    """Responde 404 si se indica una categoría que no existe (evita violar la llave foránea)."""
    if categoria_id is None:
        return
    if not db.query(Categoria.id).filter(Categoria.id == categoria_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")


def _confirmar_o_rechazar_codigo_duplicado(db: Session) -> None:
    """Confirma los cambios; si otra petición guardó el mismo código de barras a la vez, responde 400."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ese código de barras ya está registrado en otro producto.",
        )


@router.get("/", response_model=list[ProductoRespuesta])
def listar_productos(
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista todos los productos activos del inventario."""
    productos = db.query(Producto).filter(Producto.activo.is_(True)).order_by(Producto.nombre).all()
    return [_a_respuesta(p, usuario) for p in productos]


@router.get("/inventario-bajo", response_model=list[ProductoRespuesta])
def listar_productos_inventario_bajo(
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista los productos cuyo stock actual llegó o bajó del stock mínimo (alertas del dashboard)."""
    productos = (
        db.query(Producto)
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .order_by(Producto.stock_actual)
        .all()
    )
    return [_a_respuesta(p, usuario) for p in productos]


@router.get("/buscar-por-codigo/{codigo_barras}", response_model=ProductoRespuesta)
def buscar_producto_por_codigo(
    codigo_barras: str,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Busca un producto ACTIVO mediante su código de barras (usado por el escáner)."""
    producto = (
        db.query(Producto)
        .filter(Producto.codigo_barras == codigo_barras, Producto.activo.is_(True))
        .first()
    )
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return _a_respuesta(producto, usuario)


# Límite de creación: evita que una cuenta comprometida o un script registre cientos de
# productos falsos en segundos.
@router.post("/", response_model=ProductoRespuesta, status_code=status.HTTP_201_CREATED)
@limitador.limit("20/minute")
def crear_producto(
    request: Request,
    datos: ProductoCrear,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("inventario_gestionar")),
):
    """
    Registra un nuevo producto (sin imagen; esta se sube después).

    Consistencia con la eliminación lógica: un código de barras usado por un producto ACTIVO
    se rechaza (duplicado real); si lo usa un producto INACTIVO (eliminado antes), ese
    registro se reactiva y se actualiza en vez de crear una fila nueva, conservando su
    historial de compras y ventas.
    """
    _validar_categoria(db, datos.categoria_id)

    if datos.codigo_barras:
        existente = db.query(Producto).filter(Producto.codigo_barras == datos.codigo_barras).first()
        if existente and existente.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un producto activo con ese código de barras",
            )
        if existente:
            # Producto eliminado antes: se reactiva con los datos nuevos
            for campo, valor in datos.model_dump().items():
                setattr(existente, campo, valor)
            existente.activo = True
            _confirmar_o_rechazar_codigo_duplicado(db)
            db.refresh(existente)

            registrar_negocio(
                accion=f"Reactivó el producto #{existente.id} '{existente.nombre}'",
                usuario=usuario.nombre_usuario,
                detalle=f"Existencias: {existente.stock_actual}",
                request=request,
            )
            return _a_respuesta(existente, usuario)

    nuevo_producto = Producto(**datos.model_dump())
    db.add(nuevo_producto)
    _confirmar_o_rechazar_codigo_duplicado(db)
    db.refresh(nuevo_producto)
    return _a_respuesta(nuevo_producto, usuario)


@router.put("/{producto_id}", response_model=ProductoRespuesta)
def actualizar_producto(
    request: Request,
    producto_id: int,
    datos: ProductoActualizar,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("inventario_gestionar")),
):
    """Actualiza parcialmente un producto y deja registrados los cambios de precio y existencias."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    datos_actualizados = datos.model_dump(exclude_unset=True)

    if "categoria_id" in datos_actualizados:
        _validar_categoria(db, datos_actualizados["categoria_id"])

    # Bloque: el código de barras es único entre TODOS los productos (activos o eliminados)
    nuevo_codigo = datos_actualizados.get("codigo_barras")
    if nuevo_codigo:
        conflicto = (
            db.query(Producto.id, Producto.activo)
            .filter(Producto.codigo_barras == nuevo_codigo, Producto.id != producto_id)
            .first()
        )
        if conflicto:
            detalle = (
                "Ya existe otro producto activo con ese código de barras"
                if conflicto.activo
                else "Ese código de barras pertenece a un producto eliminado. "
                "Crea el producto de nuevo con ese código para reactivarlo."
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detalle)

    # Bloque: arma la lista de cambios auditables ANTES de modificar el producto
    cambios = [
        f"{campo}: {getattr(producto, campo)} -> {datos_actualizados[campo]}"
        for campo in _CAMPOS_AUDITADOS
        if campo in datos_actualizados and getattr(producto, campo) != datos_actualizados[campo]
    ]

    for campo, valor in datos_actualizados.items():
        setattr(producto, campo, valor)

    _confirmar_o_rechazar_codigo_duplicado(db)
    db.refresh(producto)

    if cambios:
        registrar_negocio(
            accion=f"Modificó el producto #{producto.id} '{producto.nombre}'",
            usuario=usuario.nombre_usuario,
            detalle="; ".join(cambios),
            request=request,
        )
    return _a_respuesta(producto, usuario)


# Límite de subida: procesar imágenes (Pillow) consume CPU; sin límite, una cuenta
# comprometida podría saturar el servidor.
@router.post("/{producto_id}/imagen", response_model=ProductoRespuesta)
@limitador.limit("30/minute")
async def subir_imagen_producto(
    request: Request,
    producto_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("inventario_gestionar")),
):
    """
    Sube (o reemplaza) la imagen de un producto existente. El archivo se valida y procesa en
    utils.imagenes_productos antes de guardarse en la base de datos. Si el producto ya tenía
    una imagen, la anterior se elimina.
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

    return _a_respuesta(producto, usuario)


@router.delete("/{producto_id}/imagen", response_model=ProductoRespuesta)
def eliminar_imagen_de_producto(
    producto_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("inventario_gestionar")),
):
    """Quita la imagen de un producto (queda sin foto, mostrando el ícono genérico)."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    eliminar_imagen_producto(producto.imagen_url)
    producto.imagen_url = None
    db.commit()
    db.refresh(producto)
    return _a_respuesta(producto, usuario)


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(
    request: Request,
    producto_id: int,
    db: Session = Depends(obtener_db),
    usuario: Usuario = Depends(requerir_permiso("inventario_gestionar")),
):
    """Desactiva un producto (eliminación lógica, conserva el historial de ventas). La imagen no se borra."""
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    producto.activo = False
    db.commit()

    registrar_negocio(
        accion=f"Eliminó (desactivó) el producto #{producto.id} '{producto.nombre}'",
        usuario=usuario.nombre_usuario,
        detalle=f"Existencias al eliminar: {producto.stock_actual}",
        request=request,
    )