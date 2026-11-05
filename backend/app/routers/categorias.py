# Ruta: backend/app/routers/categorias.py
# Endpoints para crear, listar, actualizar y eliminar categorías de productos.
#
# CAMBIOS:
# - Se agrega PUT /{categoria_id} para editar nombre y descripción.
# - Al eliminar, se rechaza si hay productos ACTIVOS en la categoría (con
#   PostgreSQL/Neon las llaves foráneas sí se hacen cumplir y daría error 500).
#   Los productos inactivos que la usaban quedan sin categoría.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.categoria import Categoria
from app.models.producto import Producto
from app.models.usuario import RolUsuario
from app.schemas.categoria import CategoriaActualizar, CategoriaCrear, CategoriaRespuesta

router = APIRouter(prefix="/api/categorias", tags=["Categorías"])


@router.get("/", response_model=list[CategoriaRespuesta])
def listar_categorias(
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR, RolUsuario.EMPLEADO)),
):
    """Lista todas las categorías registradas (visible para administradores y empleados)."""
    return db.query(Categoria).order_by(Categoria.nombre).all()


@router.post("/", response_model=CategoriaRespuesta, status_code=status.HTTP_201_CREATED)
def crear_categoria(
    datos: CategoriaCrear,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Crea una nueva categoría (solo el administrador puede hacerlo)."""
    if db.query(Categoria).filter(Categoria.nombre == datos.nombre).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe una categoría con ese nombre")

    nueva_categoria = Categoria(**datos.model_dump())
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    return nueva_categoria


@router.put("/{categoria_id}", response_model=CategoriaRespuesta)
def actualizar_categoria(
    categoria_id: int,
    datos: CategoriaActualizar,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Edita el nombre o la descripción de una categoría (solo administrador)."""
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    datos_dict = datos.model_dump(exclude_unset=True)

    # El nombre es obligatorio en la base de datos: no puede quedar vacío
    if "nombre" in datos_dict:
        if datos_dict["nombre"] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre no puede quedar vacío")
        duplicada = (
            db.query(Categoria)
            .filter(Categoria.nombre == datos_dict["nombre"], Categoria.id != categoria_id)
            .first()
        )
        if duplicada:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe una categoría con ese nombre")

    for campo, valor in datos_dict.items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(
    categoria_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Elimina una categoría, siempre que ningún producto activo la esté usando."""
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    en_uso = (
        db.query(Producto.id)
        .filter(Producto.categoria_id == categoria_id, Producto.activo.is_(True))
        .first()
    )
    if en_uso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar: hay productos asignados a esta categoría. Cámbialos de categoría primero.",
        )

    # Los productos inactivos que la usaban quedan sin categoría (conservan su historial)
    db.query(Producto).filter(Producto.categoria_id == categoria_id).update(
        {Producto.categoria_id: None}, synchronize_session=False
    )
    db.delete(categoria)
    db.commit()