# Ruta: backend/app/mesas_realtime/schemas.py
# Validación de la forma de los mensajes que llegan por el WebSocket de
# mesas. Aunque WebSocket no usa el sistema normal de Pydantic de FastAPI
# (response_model), reutilizamos Pydantic manualmente para no confiar en
# datos crudos de un socket, que es una superficie de ataque tan válida
# como cualquier endpoint HTTP.

from typing import Literal

from pydantic import BaseModel, ValidationError


class _MensajeEntranteMesas(BaseModel):
    """
    Forma válida de cualquier mensaje que un cliente puede enviar por este
    WebSocket. Los cuatro tipos de mensaje comparten la misma forma (tipo +
    mesa_id), así que un solo modelo basta.
    - bloquear_mesa / liberar_mesa / heartbeat: gestionan el bloqueo
      colaborativo (quién está atendiendo la mesa ahora mismo).
    - notificar_cambio_mesa: señal informativa (no toca el bloqueo) para
      avisar a todos los usuarios conectados que el ESTADO real de una mesa
      cambió en la base de datos (libre/ocupada/pendiente_pago) y deben
      refrescar su copia local. Se envía DESPUÉS de que una petición REST
      (abrir venta, cobrar, cancelar, etc.) ya confirmó el cambio.
    """
    tipo: Literal["bloquear_mesa", "liberar_mesa", "heartbeat", "notificar_cambio_mesa"]
    mesa_id: int


def validar_mensaje_entrante(crudo) -> tuple[dict | None, str | None]:
    """
    Valida un mensaje recibido por WebSocket antes de procesarlo.
    Devuelve (mensaje_validado, None) si es correcto, o (None, "texto del
    error") si no lo es. Nunca lanza una excepción hacia el llamador: un
    mensaje malformado de un cliente no debe tumbar la conexión de nadie.
    """
    if not isinstance(crudo, dict):
        return None, "El mensaje debe ser un objeto JSON con 'tipo' y 'mesa_id'."

    try:
        validado = _MensajeEntranteMesas(**crudo)
    except ValidationError as error:
        primer_error = error.errors()[0] if error.errors() else {}
        return None, f"Mensaje inválido: {primer_error.get('msg', 'formato incorrecto')}"

    return validado.model_dump(), None