# Ruta: backend/escaner/__init__.py
# Paquete del módulo de escáner de códigos de barras.
# Expone el router principal para que main.py lo registre en la aplicación.

from escaner.router import router  # noqa: F401 – reexportación intencional 