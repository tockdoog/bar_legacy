# Ruta: backend/scripts/migrar_permisos_usuario.py
# Script manual (opcional) para aplicar migraciones pendientes fuera del
# arranque normal del servidor, por ejemplo dentro de un contenedor Docker
# ya construido sin reiniciarlo. Reutiliza la misma lógica que se ejecuta
# automáticamente en cada arranque (ver app/utils/migraciones.py) para no
# mantener el mismo código de migración duplicado en dos lugares.
#
# Uso dentro del contenedor Docker:
#   docker compose exec backend python scripts/migrar_permisos_usuario.py
# Uso local (aplica sobre la base de datos que indique tu backend/.env):
#   python scripts/migrar_permisos_usuario.py
#
# NOTA: desde la versión que agrega la migración automática al arranque
# (ver main.py -> ciclo_de_vida), este script ya no es obligatorio. Se
# conserva por si necesitas aplicar el cambio sin reiniciar el contenedor.

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database import motor
from app.utils.migraciones import aplicar_migraciones_pendientes

if __name__ == "__main__":
    aplicar_migraciones_pendientes(motor)
    print("Migraciones aplicadas correctamente (o ya estaban al día).")