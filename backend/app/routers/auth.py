# Ruta: backend/app/routers/auth.py
# Endpoints de autenticación: inicio de sesión (login) y datos del usuario en
# sesión. Sistema de uso general, sin relación con ningún nicho de negocio
# específico.
#
# CORRECCIÓN: se reemplazó datetime.now(timezone.utc) por ahora_colombia().
# Las bases de datos (SQLite y PostgreSQL/Neon con DateTime sin zona) devuelven
# "bloqueado_hasta" como datetime sin tzinfo; compararlo con un datetime con
# zona lanzaba TypeError (error 500) justo cuando una cuenta quedaba bloqueada.

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.auth import TokenRespuesta
from app.schemas.usuario import UsuarioRespuesta
from app.security import verificar_contrasena, crear_token_acceso
from app.utils.limitador import limitador
from app.utils.zona_horaria import ahora_colombia

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# Reglas de bloqueo por intentos fallidos (mitiga ataques de fuerza bruta)
MAXIMO_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 15

# Hash bcrypt "señuelo": se usa cuando el nombre de usuario no existe, para que
# bcrypt haga el mismo trabajo y el tiempo de respuesta no delate qué usuarios
# existen (ataque de canal lateral por tiempo).
HASH_SENUELO_LOGIN = "$2b$12$C6UzMDM.H6dfI/f/IKcEeOgOWG6vNn5j6BE7z2NqW5F8kbcJ5AzGa"


@router.post("/login", response_model=TokenRespuesta)
@limitador.limit("5/minute")  # Máximo 5 intentos de login por minuto por IP
def iniciar_sesion(
    request: Request,
    credenciales: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(obtener_db),
):
    """
    Valida usuario y contraseña, y entrega un token JWT si son correctos.
    Aplica bloqueo temporal de la cuenta tras varios intentos fallidos consecutivos.
    """
    usuario = (
        db.query(Usuario)
        .filter(Usuario.nombre_usuario == credenciales.username)
        .first()
    )

    # Mensaje genérico para no revelar si el usuario existe o no
    error_login = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos",
    )

    # Verificación de contraseña SIEMPRE ejecutada, exista o no el usuario
    hash_a_comparar = usuario.contrasena_hash if usuario else HASH_SENUELO_LOGIN
    contrasena_correcta = verificar_contrasena(credenciales.password, hash_a_comparar)

    if usuario is None:
        raise error_login

    # Hora local de Colombia (sin zona), coherente con lo guardado en la BD
    ahora = ahora_colombia()

    # Verifica si la cuenta está temporalmente bloqueada
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intenta más tarde.",
        )

    if not usuario.activo or not contrasena_correcta:
        # Aumenta el contador de intentos fallidos y bloquea la cuenta si se supera el límite
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= MAXIMO_INTENTOS_FALLIDOS:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
            usuario.intentos_fallidos = 0
        db.commit()
        raise error_login

    # Login correcto: se reinicia el contador de intentos fallidos
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    db.commit()

    token = crear_token_acceso({"id_usuario": usuario.id, "rol": usuario.rol.value})

    return TokenRespuesta(
        token_acceso=token,
        rol=usuario.rol.value,
        nombre_completo=usuario.nombre_completo,
        permisos=usuario.permisos_lista,
    )


@router.get("/yo", response_model=UsuarioRespuesta)
def obtener_perfil_actual(usuario: Usuario = Depends(obtener_usuario_actual)):
    """Devuelve los datos del usuario actualmente autenticado (útil para el frontend)."""
    return usuario