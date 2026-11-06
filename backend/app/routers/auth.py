# Ruta: backend/app/routers/auth.py
# Endpoints de autenticación: inicio de sesión (login) y datos del usuario en
# sesión. Sistema de uso general, sin relación con ningún nicho de negocio.
#
# PROTECCIÓN CONTRA FUERZA BRUTA (tres capas):
#   1. slowapi: 5 intentos por minuto por IP (en Vercel cuenta por instancia, es débil).
#   2. Bloqueo de la cuenta tras 5 fallos consecutivos (guardado en la base de datos).
#   3. Límite por IP guardado en la base de datos (tabla intentos_login): compartido
#      entre todas las instancias y efectivo contra quien prueba muchos usuarios.
#
# Las fechas usan ahora_colombia() (sin zona): las bases devuelven DateTime sin
# tzinfo y compararlas con fechas con zona lanzaba TypeError (error 500).

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import obtener_usuario_actual
from app.models.intento_login import IntentoLogin
from app.models.usuario import Usuario
from app.schemas.auth import TokenRespuesta
from app.schemas.usuario import UsuarioRespuesta
from app.security import verificar_contrasena, crear_token_acceso
from app.utils.limitador import limitador, obtener_ip_cliente
from app.utils.zona_horaria import ahora_colombia

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# Reglas de bloqueo por intentos fallidos de una CUENTA
MAXIMO_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 15

# Reglas de bloqueo por intentos fallidos desde una IP (cualquier usuario)
MAXIMO_FALLOS_POR_IP = 20
VENTANA_MINUTOS_POR_IP = 15
DIAS_CONSERVAR_INTENTOS = 1

# Hash bcrypt "señuelo": se usa cuando el nombre de usuario no existe, para que
# bcrypt haga el mismo trabajo y el tiempo de respuesta no delate qué usuarios
# existen (ataque de canal lateral por tiempo).
HASH_SENUELO_LOGIN = "$2b$12$C6UzMDM.H6dfI/f/IKcEeOgOWG6vNn5j6BE7z2NqW5F8kbcJ5AzGa"


def _verificar_limite_por_ip(db: Session, ip: str, ahora: datetime) -> None:
    """Rechaza con 429 si la IP acumuló demasiados fallos recientes (antes de gastar CPU en bcrypt)."""
    limite = ahora - timedelta(minutes=VENTANA_MINUTOS_POR_IP)
    fallos = (
        db.query(func.count(IntentoLogin.id))
        .filter(IntentoLogin.ip == ip, IntentoLogin.fecha >= limite)
        .scalar()
        or 0
    )
    if fallos >= MAXIMO_FALLOS_POR_IP:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos desde tu red. Intenta de nuevo en unos minutos.",
        )


def _anotar_fallo_de_ip(db: Session, ip: str, ahora: datetime) -> None:
    """Agrega un fallo para la IP y borra los antiguos. El llamador es quien confirma (commit)."""
    db.add(IntentoLogin(ip=ip[:64], fecha=ahora))
    db.query(IntentoLogin).filter(
        IntentoLogin.fecha < ahora - timedelta(days=DIAS_CONSERVAR_INTENTOS)
    ).delete(synchronize_session=False)


@router.post("/login", response_model=TokenRespuesta)
@limitador.limit("5/minute")  # Máximo 5 intentos de login por minuto por IP (por instancia)
def iniciar_sesion(
    request: Request,
    credenciales: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(obtener_db),
):
    """
    Valida usuario y contraseña, y entrega un token JWT si son correctos.
    Aplica bloqueo temporal de la cuenta y de la IP tras varios intentos fallidos.
    """
    ip = obtener_ip_cliente(request)
    ahora = ahora_colombia()  # Hora local de Colombia (sin zona), coherente con la BD

    # Bloque: límite por IP, antes de cualquier trabajo costoso
    _verificar_limite_por_ip(db, ip, ahora)

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

    # Bloque: usuario inexistente. Cuenta como fallo de la IP (frena el rastreo de usuarios)
    if usuario is None:
        _anotar_fallo_de_ip(db, ip, ahora)
        db.commit()
        raise error_login

    # Bloque: cuenta temporalmente bloqueada
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente por demasiados intentos fallidos. Intenta más tarde.",
        )

    # Bloque: credenciales incorrectas o cuenta inactiva
    if not usuario.activo or not contrasena_correcta:
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= MAXIMO_INTENTOS_FALLIDOS:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
            usuario.intentos_fallidos = 0
        _anotar_fallo_de_ip(db, ip, ahora)
        db.commit()
        raise error_login

    # Bloque: login correcto, se reinicia el contador de intentos fallidos de la cuenta
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