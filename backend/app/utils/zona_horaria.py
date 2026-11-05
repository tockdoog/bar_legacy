# Ruta: backend/app/utils/zona_horaria.py
# Utilidad central para el manejo de fechas y horas del sistema en la zona
# horaria de Colombia (America/Bogota, UTC-5, sin horario de verano).
#
# PROBLEMA QUE RESUELVE (bug de "la venta se guarda un dia despues"):
# SQLite (motor de base de datos del sistema) no conserva informacion de
# zona horaria: al guardar un datetime "aware" (con tzinfo, ej. UTC) en una
# columna DateTime, SQLAlchemy lo recupera despues como un datetime "naive"
# (sin tzinfo), pero con el MISMO NUMERO que se guardo. El sistema mezclaba
# `datetime.now(timezone.utc)` para GUARDAR ventas (hora UTC) con
# `date.today()` para FILTRAR reportes (hora del sistema operativo del
# contenedor, que dentro de Docker normalmente esta en UTC). Resultado
# practico: una venta hecha de noche en Colombia (UTC-5) quedaba guardada
# con fecha del DIA SIGUIENTE en UTC, y aparecia en el reporte del dia
# equivocado (o el usuario la veia con fecha "de mañana").
#
# SOLUCION: todo el sistema usa SIEMPRE la hora local de Colombia (naive,
# sin tzinfo) tanto para guardar en la base de datos como para calcular los
# rangos de fecha de los reportes y mostrarla en pantalla/Excel/PDF. Al ser
# un sistema pensado para un unico pais/zona horaria, esto evita el
# problema de raiz sin depender de que SQLite conserve tzinfo (no lo hace)
# ni de que el servidor este configurado en una zona horaria especifica.
#
# IMPORTANTE PARA QUIEN EXTIENDA EL SISTEMA: cualquier archivo nuevo que
# necesite la fecha/hora "actual" para guardar un registro (compras,
# escaneos, logs, promociones, etc.) DEBE usar ahora_colombia() de este
# modulo, nunca datetime.now(), datetime.now(timezone.utc) ni
# datetime.utcnow() directamente, para mantener la coherencia de fechas en
# todo el sistema.

from datetime import datetime
from zoneinfo import ZoneInfo

# Zona horaria oficial de Colombia. No tiene horario de verano, por lo que
# su desfase respecto a UTC (-05:00) es constante durante todo el año.
ZONA_HORARIA_COLOMBIA = ZoneInfo("America/Bogota")


def ahora_colombia() -> datetime:
    """
    Devuelve la fecha y hora actual en Colombia como un datetime "naive"
    (sin tzinfo), lista para guardarse directamente en una columna DateTime
    de SQLAlchemy/SQLite sin sufrir desfases al leerla de vuelta.
    """
    return datetime.now(ZONA_HORARIA_COLOMBIA).replace(tzinfo=None)


def hoy_colombia():
    """
    Devuelve la fecha (sin hora) actual en Colombia. Debe usarse en vez de
    `date.today()` como valor por defecto en los reportes, ya que
    `date.today()` toma la fecha del sistema operativo del servidor
    (dentro de Docker normalmente es UTC, hasta 5 horas adelante de la
    hora real de Colombia).
    """
    return ahora_colombia().date()