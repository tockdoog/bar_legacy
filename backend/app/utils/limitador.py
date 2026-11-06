# Ruta: backend/app/utils/limitador.py
# Configura el limitador de peticiones (rate limiting) usado para proteger
# endpoints sensibles, como el inicio de sesión, contra ataques de fuerza bruta.
#
# En Vercel, get_remote_address devuelve la IP del proxy y todos los usuarios
# compartirían el mismo contador. Allí se toma la IP real de X-Forwarded-For
# (Vercel la sobrescribe, el cliente no la puede falsificar). Fuera de Vercel se
# usa la IP de la conexión, porque confiar en esa cabecera sin un proxy propio
# permitiría saltarse el límite.
#
# LIMITACIÓN: slowapi cuenta en la memoria de cada instancia, que en Vercel no se
# comparte. Por eso el login además guarda sus fallos en la base de datos
# (ver models/intento_login.py y routers/auth.py).

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_EN_VERCEL = bool(os.environ.get("VERCEL"))


def obtener_ip_cliente(request) -> str:
    """IP del cliente, usada como llave del límite de peticiones y en los registros de seguridad."""
    if _EN_VERCEL:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip()
    return get_remote_address(request)


# Instancia única del limitador, registrada en app.state.limiter (ver main.py)
limitador = Limiter(key_func=obtener_ip_cliente)