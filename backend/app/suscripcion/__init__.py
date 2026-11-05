# Ruta: backend/app/suscripcion/__init__.py
# Paquete del módulo de suscripción y bloqueo por pago mensual.
# Expone el router principal para que main.py lo registre en la aplicación,
# siguiendo el mismo patrón que el módulo backend/escaner/.

from app.suscripcion.router import router  # noqa: F401 – reexportación intencional