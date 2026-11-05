# Ruta: backend/app/mesas_realtime/router.py
# Endpoint WebSocket que sincroniza en tiempo real el bloqueo de mesas
# entre todos los usuarios conectados. Autenticación por token JWT enviado
# como parámetro de consulta (?token=...) porque el navegador no permite
# enviar cabeceras personalizadas (como Authorization) al abrir un WebSocket.
#
# SEGURIDAD:
# - Se valida el token igual que en las peticiones HTTP normales (mismo
#   decodificador de app/security.py) antes de aceptar la conexión.
# - Se valida la cabecera Origin contra los orígenes CORS permitidos, como
#   defensa adicional (un WebSocket no pasa por el middleware de CORS de
#   FastAPI, que solo aplica a peticiones HTTP normales).
# - Se limita la cantidad de mensajes por conexión por minuto, para mitigar
#   un cliente malicioso o con errores que intente inundar el servidor.
# - Cada mensaje entrante se valida con Pydantic (ver schemas.py) antes de
#   procesarse; un mensaje malformado nunca tumba la conexión.

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import configuracion
from app.database import SesionLocal
from app.models.mesa import Mesa
from app.models.usuario import Usuario
from app.security import decodificar_token
from app.mesas_realtime.gestor_bloqueos import gestor_bloqueos_mesas
from app.mesas_realtime.schemas import validar_mensaje_entrante

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/mesas", tags=["Mesas - Tiempo real"])

# Límite defensivo de mensajes por conexión, para mitigar abuso/flood
LIMITE_MENSAJES_POR_MINUTO = 120


async def _autenticar_conexion(websocket: WebSocket) -> Usuario | None:
    """
    Decodifica el token recibido por query string y busca al usuario en la
    base de datos, igual que hace obtener_usuario_actual() para peticiones
    HTTP normales (ver app/dependencies.py), pero de forma manual porque
    Depends(OAuth2PasswordBearer) no aplica a conexiones WebSocket.
    """
    token = websocket.query_params.get("token")
    if not token:
        return None

    datos = decodificar_token(token)
    if not datos or "id_usuario" not in datos:
        return None

    try:
        id_usuario = int(datos["id_usuario"])
    except (TypeError, ValueError):
        return None

    db = SesionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.id == id_usuario).first()
        if usuario is None or not usuario.activo:
            return None
        return usuario
    finally:
        db.close()


def _origen_permitido(websocket: WebSocket) -> bool:
    """Verifica que la cabecera Origin (si viene) esté en la lista de orígenes CORS permitidos."""
    origen = websocket.headers.get("origin")
    if not origen:
        # Conexiones sin cabecera Origin (ej. herramientas que no son
        # navegador) ya pasan por la autenticación de token; se aceptan aquí.
        return True
    return origen in configuracion.lista_origenes_cors


@router.websocket("/ws")
async def websocket_estado_mesas(websocket: WebSocket):
    """
    Canal de tiempo real para el bloqueo colaborativo de mesas y la
    sincronización de su estado real (libre/ocupada/pendiente_pago).

    Mensajes que el cliente puede enviar:
      {"tipo": "bloquear_mesa", "mesa_id": N}
      {"tipo": "liberar_mesa", "mesa_id": N}
      {"tipo": "heartbeat", "mesa_id": N}
      {"tipo": "notificar_cambio_mesa", "mesa_id": N}

    Mensajes que el servidor puede enviar:
      {"tipo": "estado_inicial", "bloqueos": [{mesa_id, usuario_id, nombre_completo, nombre_usuario, desde}, ...]}
      {"tipo": "bloqueo_confirmado", "mesa_id": N, "desde": iso}
      {"tipo": "bloqueo_rechazado", "mesa_id": N, "usuario_id": N, "nombre_completo": str, "nombre_usuario": str, "desde": iso}
      {"tipo": "mesa_bloqueada", "mesa_id": N, "usuario_id": N, "nombre_completo": str, "nombre_usuario": str, "desde": iso}
      {"tipo": "mesa_liberada", "mesa_id": N, "motivo": str}
      {"tipo": "mesa_actualizada", "mesa_id": N}
      {"tipo": "intento_acceso", "mesa_id": N, "nombre_completo_intento": str}
      {"tipo": "error", "detalle": str}
    """
    if not _origen_permitido(websocket):
        await websocket.close(code=4403)
        return

    usuario = await _autenticar_conexion(websocket)
    if usuario is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await gestor_bloqueos_mesas.conectar(usuario.id, websocket)

    # Bloque: al conectarse, se envía el estado completo de bloqueos
    # vigentes para que el navegador pinte de inmediato quién tiene qué mesa
    estado_inicial = await gestor_bloqueos_mesas.obtener_estado()
    await websocket.send_json({"tipo": "estado_inicial", "bloqueos": estado_inicial})

    # Bloque: contador simple de mensajes por minuto (mitiga flood/abuso)
    mensajes_recibidos = 0
    ventana_inicio = asyncio.get_event_loop().time()

    try:
        while True:
            crudo = await websocket.receive_json()

            ahora = asyncio.get_event_loop().time()
            if ahora - ventana_inicio > 60:
                ventana_inicio = ahora
                mensajes_recibidos = 0
            mensajes_recibidos += 1
            if mensajes_recibidos > LIMITE_MENSAJES_POR_MINUTO:
                await websocket.send_json(
                    {"tipo": "error", "detalle": "Demasiados mensajes, intenta más despacio."}
                )
                continue

            mensaje_valido, error_validacion = validar_mensaje_entrante(crudo)
            if error_validacion:
                await websocket.send_json({"tipo": "error", "detalle": error_validacion})
                continue

            await _procesar_mensaje(websocket, usuario, mensaje_valido)

    except WebSocketDisconnect:
        pass
    except Exception as excepcion:
        logger.error(f"Error en WebSocket de mesas (usuario {usuario.id}): {excepcion}")
    finally:
        # Bloque: al desconectarse (cierre normal, error o pestaña cerrada),
        # se liberan automáticamente las mesas que esta conexión tenía
        # bloqueadas y se avisa a todos los demás usuarios conectados.
        mesas_liberadas = await gestor_bloqueos_mesas.desconectar(websocket)
        for mesa_id in mesas_liberadas:
            await gestor_bloqueos_mesas.difundir_a_todos(
                {"tipo": "mesa_liberada", "mesa_id": mesa_id, "motivo": "usuario_desconectado"}
            )


async def _procesar_mensaje(websocket: WebSocket, usuario: Usuario, mensaje: dict) -> None:
    """Despacha un mensaje ya validado según su 'tipo' hacia la acción correspondiente."""
    tipo = mensaje["tipo"]
    mesa_id = mensaje["mesa_id"]

    if tipo == "bloquear_mesa":
        # Bloque: se valida que la mesa exista de verdad en la base de
        # datos antes de bloquearla en memoria (evita bloqueos "fantasma"
        # de mesas inexistentes o ya eliminadas).
        db = SesionLocal()
        try:
            existe_mesa = db.query(Mesa.id).filter(Mesa.id == mesa_id).first()
        finally:
            db.close()

        if not existe_mesa:
            await websocket.send_json({"tipo": "error", "detalle": "La mesa indicada no existe."})
            return

        concedido, info = await gestor_bloqueos_mesas.intentar_bloquear(
            mesa_id, usuario.id, usuario.nombre_completo, usuario.nombre_usuario, websocket
        )

        if concedido:
            # Confirma al que solicitó, y avisa a todos los demás que la
            # mesa ya tiene dueño (para que su plano se pinte en gris/bloqueada)
            await websocket.send_json(
                {"tipo": "bloqueo_confirmado", "mesa_id": mesa_id, "desde": info.desde.isoformat()}
            )
            await gestor_bloqueos_mesas.difundir_a_todos(
                {
                    "tipo": "mesa_bloqueada",
                    "mesa_id": mesa_id,
                    "usuario_id": usuario.id,
                    "nombre_completo": usuario.nombre_completo,
                    "nombre_usuario": usuario.nombre_usuario,
                    "desde": info.desde.isoformat(),
                },
                excluir=websocket,
            )
        else:
            # Rechaza al solicitante indicando quién tiene la mesa y desde
            # cuándo (con AMBOS nombres, para que el frontend decida cuál
            # mostrar en cada lugar: nombre_usuario en la insignia de la
            # mesa, nombre_completo en la alerta emergente), y avisa en
            # tiempo real a quien la tiene que alguien más intentó acceder.
            await websocket.send_json(
                {
                    "tipo": "bloqueo_rechazado",
                    "mesa_id": mesa_id,
                    "usuario_id": info.usuario_id,
                    "nombre_completo": info.nombre_completo,
                    "nombre_usuario": info.nombre_usuario,
                    "desde": info.desde.isoformat(),
                }
            )
            await gestor_bloqueos_mesas.enviar_a_usuario(
                info.usuario_id,
                {
                    "tipo": "intento_acceso",
                    "mesa_id": mesa_id,
                    # Se envía el nombre COMPLETO (no el de usuario) porque
                    # este mensaje siempre se muestra como una alerta.
                    "nombre_completo_intento": usuario.nombre_completo,
                },
            )

    elif tipo == "liberar_mesa":
        liberado = await gestor_bloqueos_mesas.liberar(mesa_id, usuario.id)
        if liberado:
            await gestor_bloqueos_mesas.difundir_a_todos(
                {"tipo": "mesa_liberada", "mesa_id": mesa_id, "motivo": "liberada_por_usuario"}
            )

    elif tipo == "heartbeat":
        # El heartbeat no genera respuesta ni difusión: solo renueva el
        # tiempo de vida del bloqueo para que no expire por inactividad.
        await gestor_bloqueos_mesas.registrar_latido(mesa_id, usuario.id)

    elif tipo == "notificar_cambio_mesa":
        # Bloque: señal puramente informativa, SIN relación con el bloqueo.
        # El frontend la envía justo después de que una petición REST (abrir
        # venta, marcar pendiente de pago, cobrar, cancelar, crear/editar/
        # eliminar mesa) ya confirmó un cambio real en la base de datos.
        # Se difunde a TODOS (incluido quien la envió, es inofensivo) para
        # que cada usuario conectado vuelva a pedir la lista de mesas y así
        # el color/estado se actualice sin recargar la página.
        #
        # Se envía DESPUÉS de la confirmación del REST (no en el momento de
        # tomar el bloqueo) para evitar la condición de carrera donde otros
        # usuarios refrescarían el estado de la mesa ANTES de que el backend
        # terminara de aplicar el cambio real (ej. al abrir una mesa, el
        # bloqueo se toma antes de crear la venta; si el refresco dependiera
        # solo del bloqueo, mostraría la mesa como "libre" todavía).
        await gestor_bloqueos_mesas.difundir_a_todos(
            {"tipo": "mesa_actualizada", "mesa_id": mesa_id}
        )