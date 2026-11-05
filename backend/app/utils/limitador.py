# Ruta: backend/app/utils/limitador.py
# Configura el limitador de peticiones (rate limiting) usado para proteger
# endpoints sensibles, como el inicio de sesión, contra ataques de fuerza bruta.

from slowapi import Limiter
from slowapi.util import get_remote_address

# Limita las peticiones según la dirección IP de origen
limitador = Limiter(key_func=get_remote_address)