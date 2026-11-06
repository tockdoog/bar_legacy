# Ruta: backend/app/utils/limitador.py
# Configura el limitador de peticiones (rate limiting) usado para proteger
# endpoints sensibles, como el inicio de sesión, contra ataques de fuerza bruta.
#
# CORRECCIÓN: detrás del proxy de Vercel, get_remote_address devuelve la IP del
# proxy y todos los usuarios compartirían el mismo contador. En Vercel se toma
# la IP real de X-Forwarded-For (Vercel la sobrescribe, el cliente no la puede
# falsificar). Fuera de Vercel se mantiene la IP de la conexión, porque confiar
# en esa cabecera sin un proxy propio permitiría saltarse el límite.

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_EN_VERCEL = bool(os.environ.get("VERCEL"))


def _ip_del_cliente(request) -> str:
    """Obtiene la IP que se usa como llave del límite de peticiones."""
    if _EN_VERCEL:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip()
    return get_remote_address(request)


limitador = Limiter(key_func=_ip_del_cliente)