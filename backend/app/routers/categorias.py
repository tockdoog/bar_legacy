# Ruta: backend/app/routers/categorias.py
# Endpoints para crear, listar, actualizar y eliminar categorías de productos.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_rol
from app.models.categoria import Categoria
from app.models.usuario import RolUsuario
from app.schemas.categoria import CategoriaCrear, CategoriaRespuesta

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


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(
    categoria_id: int,
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_rol(RolUsuario.ADMINISTRADOR)),
):
    """Elimina una categoría existente por su id."""
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    db.delete(categoria)
    db.commit()