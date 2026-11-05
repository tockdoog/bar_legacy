# Ruta: backend/api/index.py
# Punto de entrada que Vercel ejecuta como función serverless. Solo expone la
# aplicación FastAPI definida en app/main.py bajo el nombre "app".

import os
import sys

# Bloque: agrega la raíz del backend al path de Python para poder importar
# los paquetes "app", "escaner" y "QR" desde esta carpeta.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401