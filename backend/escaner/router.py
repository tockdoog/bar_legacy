# Ruta: backend/escaner/router.py
# Router FastAPI del modulo de escanador de codigos de barras.
# Expone endpoints seguros para:
#   - Buscar un producto activo por su codigo de barras (GET).
#   - Registrar cada evento de escaneo en la base de datos para auditoría y reportes (POST).
#
# Seguridad aplicada:
#   - Todos los endpoints requieren token JWT valido (requerir_rol).
#   - El codigo de barras se valida con regex antes de consultar la BD.
#   - Los logs de auditoría usan hash SHA-256 del codigo, nunca el valor en claro.
#   - Rate limiting por IP heredado del limitador global de la aplicacion.
#   - SQLAlchemy usa parametros enlazados: el codigo nunca se interpola en SQL.
#
# CAMBIOS EN ESTA VERSION:
#   - El costo de compra (precio_compra) solo se devuelve a quien puede ver costos
#     (administrador o permiso "inventario_gestionar"); para el resto sale en None.
#   - La fecha del evento se guarda con ahora_colombia() (hora local de Colombia),
#     coherente con ventas y compras.

import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.producto import Producto
from app.models.usuario import RolUsuario
from app.utils.limitador import limitador
from app.utils.zona_horaria import ahora_colombia
from escaner.models import EscaneoLog
from escaner.schemas import ResultadoEscaneo, RegistroEscaneoBitacora

# Logger especifico del modulo de escanador (aparece etiquetado en los logs del servidor)
logger = logging.getLogger("escaner")

router = APIRouter(prefix="/api/escaner", tags=["Escaner"])

# Patron de validacion de codigo de barras: letras, numeros y guiones, max 64 chars.
PATRON_CODIGO_VALIDO = re.compile(r"^[A-Za-z0-9\-]{1,64}$")


def _validar_codigo(codigo: str) -> None:
    """
    Valida el formato del codigo de barras recibido antes de consultar la BD.
    Lanza HTTP 422 si el codigo esta vacio, es demasiado largo o tiene caracteres
    no permitidos. Es la primera linea de defensa contra entradas maliciosas.
    """
    if not codigo or not PATRON_CODIGO_VALIDO.match(codigo):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Codigo de barras invalido. Solo se permiten letras, numeros y guiones, "
                "con un maximo de 64 caracteres."
            ),
        )


def _hash_codigo(codigo: str) -> str:
    """
    Genera un hash SHA-256 truncado del codigo de barras para los logs de auditoria
    (primeros 16 caracteres hex), sin exponer el valor real del codigo.
    """
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()[:16]


def _puede_ver_costos(usuario) -> bool:
    """El administrador y quien gestiona el inventario pueden ver el costo de compra."""
    return usuario.rol == RolUsuario.ADMINISTRADOR or "inventario_gestionar" in usuario.permisos_lista


# ---------------------------------------------------------------------------
# GET /api/escaner/codigo/{codigo_barras}
# Busca un producto activo por codigo de barras.
# Devuelve encontrado=False en lugar de 404 para simplificar el manejo en frontend.
# ---------------------------------------------------------------------------
@router.get(
    "/codigo/{codigo_barras}",
    response_model=ResultadoEscaneo,
    summary="Buscar producto por codigo de barras",
)
@limitador.limit("60/minute")
def buscar_por_codigo_de_barras(
    request: Request,
    codigo_barras: str,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
) -> ResultadoEscaneo:
    """
    Busca un producto activo en el inventario por su codigo de barras.
    Retorna los datos del producto si existe, o encontrado=False si no.
    """
    # Valida el formato del codigo antes de tocar la base de datos
    _validar_codigo(codigo_barras)

    # Registro en log del servidor usando hash, nunca el codigo real
    logger.info(
        "Escaneo recibido | usuario=%s | codigo_hash=%s",
        usuario.nombre_usuario,
        _hash_codigo(codigo_barras),
    )

    # Consulta segura con parametros enlazados (SQLAlchemy previene SQL injection)
    producto = (
        db.query(Producto)
        .filter(
            Producto.codigo_barras == codigo_barras,
            Producto.activo.is_(True),
        )
        .first()
    )

    if not producto:
        logger.warning("Codigo no encontrado | codigo_hash=%s", _hash_codigo(codigo_barras))
        return ResultadoEscaneo(encontrado=False)

    # Construccion manual de la respuesta para no exponer campos internos del ORM.
    # El costo de compra solo se incluye si el usuario puede verlo.
    return ResultadoEscaneo(
        encontrado=True,
        id=producto.id,
        nombre=producto.nombre,
        codigo_barras=producto.codigo_barras,
        precio_venta=producto.precio_venta,
        precio_compra=producto.precio_compra if _puede_ver_costos(usuario) else None,
        stock_actual=producto.stock_actual,
        stock_minimo=producto.stock_minimo,
        presentacion=producto.presentacion,
        categoria_id=producto.categoria_id,
        imagen_url=producto.imagen_url,
    )


# ---------------------------------------------------------------------------
# POST /api/escaner/bitacora
# Guarda cada evento de escaneo en la tabla escaneos_log para auditoría y reportes.
# No modifica el inventario: es exclusivamente un registro de actividad.
# ---------------------------------------------------------------------------
@router.post(
    "/bitacora",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar evento de escaneo en la bitacora",
)
@limitador.limit("120/minute")
def registrar_evento_escaneo(
    request: Request,
    datos: RegistroEscaneoBitacora,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
) -> None:
    """
    Persiste en la base de datos un evento de escaneo enviado por el frontend.
    Guarda el codigo real solo cuando el producto fue encontrado (dato ya conocido).
    Cuando no se encontro el producto guarda NULL para no revelar intentos fallidos.
    """
    # Valida el modulo de origen para evitar valores arbitrarios en la BD
    origenes_validos = {"inventario", "pos", "compras"}
    modulo_seguro = datos.origen if datos.origen in origenes_validos else "desconocido"

    producto_id = None
    codigo_a_guardar = None

    if datos.encontrado:
        # Solo busca el producto si el frontend reporto que fue encontrado
        producto = (
            db.query(Producto)
            .filter(
                Producto.codigo_barras == datos.codigo_escaneado,
                Producto.activo.is_(True),
            )
            .first()
        )
        if producto:
            producto_id = producto.id
            codigo_a_guardar = datos.codigo_escaneado

    # Registro de auditoria con la fecha en hora local de Colombia
    evento = EscaneoLog(
        codigo_hash=_hash_codigo(datos.codigo_escaneado),
        codigo_barras=codigo_a_guardar,
        modulo_origen=modulo_seguro,
        encontrado=datos.encontrado,
        usuario_id=usuario.id,
        producto_id=producto_id,
        fecha=ahora_colombia(),
    )
    db.add(evento)
    db.commit()

    logger.info(
        "Bitacora escaneo | usuario=%s | hash=%s | modulo=%s | encontrado=%s",
        usuario.nombre_usuario,
        _hash_codigo(datos.codigo_escaneado),
        modulo_seguro,
        datos.encontrado,
    )