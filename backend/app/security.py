# Ruta: backend/app/security.py
# Funciones de seguridad reutilizables: cifrado de contraseñas (bcrypt) y
# generación/verificación de tokens JWT para la autenticación de usuarios.
# Sistema de uso general, sin relación con ningún nicho de negocio específico.

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import configuracion

# --- Contexto de cifrado de contraseñas ---
# Se usa bcrypt porque incluye "salt" automático y es resistente a ataques de fuerza bruta.
contexto_contrasenas = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt solo procesa los primeros 72 BYTES de la contraseña: cualquier
# caracter despues de ese limite se ignora silenciosamente. Sin esta
# validacion, dos contraseñas distintas que compartan los primeros 72 bytes
# serian tratadas como iguales, dando una falsa sensacion de seguridad al
# usuario que eligio una contraseña "larga".
LIMITE_BYTES_CONTRASENA = 72


def cifrar_contrasena(contrasena_plana: str) -> str:
    """
    Convierte una contraseña en texto plano en un hash seguro antes de guardarla.
    Rechaza contraseñas que superen el límite real de bcrypt (72 bytes) para
    no truncarlas de forma silenciosa.
    """
    if len(contrasena_plana.encode("utf-8")) > LIMITE_BYTES_CONTRASENA:
        raise ValueError(
            f"La contraseña no puede superar los {LIMITE_BYTES_CONTRASENA} bytes de longitud."
        )
    return contexto_contrasenas.hash(contrasena_plana)


def verificar_contrasena(contrasena_plana: str, contrasena_hash: str) -> bool:
    """
    Compara una contraseña en texto plano contra el hash guardado en la base de datos.
    Envuelto en try/except: si el hash almacenado estuviera corrupto o en un
    formato inesperado, passlib lanza una excepción en lugar de "False"; se
    captura para que el login responda con un error controlado (401) en vez
    de un error 500 que expondría detalles internos del servidor.
    """
    try:
        return contexto_contrasenas.verify(contrasena_plana, contrasena_hash)
    except (ValueError, TypeError):
        return False


def crear_token_acceso(datos: dict, minutos_expiracion: int | None = None) -> str:
    """
    Genera un token JWT firmado que representa la sesión de un usuario autenticado.
    Incluye "iat" (fecha de emisión) ademas de "exp" (fecha de expiración):
    el "iat" permite, si en el futuro se necesita, invalidar todos los
    tokens emitidos antes de cierta fecha (por ejemplo, tras un cambio de
    contraseña o una sospecha de robo de sesión).
    """
    a_codificar = datos.copy()
    ahora = datetime.now(timezone.utc)
    expiracion = ahora + timedelta(
        minutes=minutos_expiracion or configuracion.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    a_codificar.update({"iat": ahora, "exp": expiracion})
    token_jwt = jwt.encode(a_codificar, configuracion.SECRET_KEY, algorithm=configuracion.ALGORITHM)
    return token_jwt


def decodificar_token(token: str) -> dict | None:
    """
    Valida la firma y la expiración de un token JWT.
    Retorna el contenido del token si es válido, o None si fue alterado o expiró.
    JWTError cubre tanto la firma inválida como el token expirado o mal formado.
    """
    try:
        return jwt.decode(token, configuracion.SECRET_KEY, algorithms=[configuracion.ALGORITHM])
    except JWTError:
        return None