# Ruta: backend/app/mesas_realtime/gestor_bloqueos.py
# Núcleo del bloqueo colaborativo: mantiene en memoria qué mesa está
# bloqueada, por quién (nombre completo Y nombre de usuario) y desde cuándo,
# además del registro de conexiones WebSocket activas para poder difundir
# cambios a todos los usuarios o avisar directamente a uno solo (ej.
# "alguien intentó entrar a tu mesa"). Toda la clase usa un asyncio.Lock
# para que dos peticiones simultáneas (dos meseros tocando la misma mesa al
# mismo milisegundo) no generen una condición de carrera donde ambas creen
# haber ganado el bloqueo.

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import WebSocket

from app.config import configuracion


@dataclass
class InfoBloqueoMesa:
    """
    Representa el bloqueo activo de una mesa: quién la tiene y desde cuándo.
    Se guardan DOS formas del nombre del usuario porque se usan en lugares
    distintos de la interfaz:
    - nombre_completo: para las alertas/notificaciones ("María intentó...").
    - nombre_usuario: el nombre de acceso corto, para la insignia visual
      sobre la mesa en el plano (menos intrusivo que el nombre completo).
    """
    mesa_id: int
    usuario_id: int
    nombre_completo: str
    nombre_usuario: str
    desde: datetime
    ultimo_latido: datetime
    websocket: WebSocket

    def a_diccionario_publico(self) -> dict:
        """Versión serializable en JSON, sin exponer el objeto WebSocket interno."""
        return {
            "mesa_id": self.mesa_id,
            "usuario_id": self.usuario_id,
            "nombre_completo": self.nombre_completo,
            "nombre_usuario": self.nombre_usuario,
            "desde": self.desde.isoformat(),
        }


class GestorBloqueosMesas:
    """
    Registro central (en memoria) de bloqueos de mesa y conexiones
    WebSocket activas. Pensado como instancia única (singleton) compartida
    por toda la aplicación durante su tiempo de vida.
    """

    def __init__(self):
        self._bloqueos: dict[int, InfoBloqueoMesa] = {}
        self._conexiones_por_usuario: dict[int, set[WebSocket]] = {}
        self._todas_las_conexiones: set[WebSocket] = set()
        # Un único candado protege todas las operaciones sobre los
        # diccionarios anteriores, evitando condiciones de carrera cuando
        # varias conexiones actúan al mismo tiempo sobre el mismo estado.
        self._candado = asyncio.Lock()

    async def conectar(self, usuario_id: int, websocket: WebSocket) -> None:
        """Registra una nueva conexión WebSocket ya autenticada y aceptada."""
        async with self._candado:
            self._todas_las_conexiones.add(websocket)
            self._conexiones_por_usuario.setdefault(usuario_id, set()).add(websocket)

    async def desconectar(self, websocket: WebSocket) -> list[int]:
        """
        Retira una conexión cerrada de todos los registros y libera
        automáticamente cualquier mesa que esa conexión tuviera bloqueada
        (por ejemplo, si el usuario cerró la pestaña del navegador sin
        cerrar la mesa correctamente desde la interfaz). Devuelve los ids
        de las mesas liberadas para que el router avise a los demás.
        """
        mesas_liberadas: list[int] = []
        async with self._candado:
            self._todas_las_conexiones.discard(websocket)

            for usuario_id, conexiones in list(self._conexiones_por_usuario.items()):
                conexiones.discard(websocket)
                if not conexiones:
                    del self._conexiones_por_usuario[usuario_id]

            for mesa_id, info in list(self._bloqueos.items()):
                if info.websocket is websocket:
                    del self._bloqueos[mesa_id]
                    mesas_liberadas.append(mesa_id)

        return mesas_liberadas

    async def intentar_bloquear(
        self,
        mesa_id: int,
        usuario_id: int,
        nombre_completo: str,
        nombre_usuario: str,
        websocket: WebSocket,
    ) -> tuple[bool, InfoBloqueoMesa]:
        """
        Intenta tomar el control exclusivo de una mesa.
        - Si nadie la tiene, o el mismo usuario ya la tenía (ej. recargó la
          página), se concede/renueva el bloqueo.
        - Si otro usuario ya la tiene, se rechaza y se devuelve su información
          (nombres y desde cuándo) para poder mostrarla en la alerta.
        Devuelve (concedido, info_del_bloqueo_vigente).
        """
        ahora = datetime.now(timezone.utc)
        async with self._candado:
            existente = self._bloqueos.get(mesa_id)

            if existente is None or existente.usuario_id == usuario_id:
                nuevo_bloqueo = InfoBloqueoMesa(
                    mesa_id=mesa_id,
                    usuario_id=usuario_id,
                    nombre_completo=nombre_completo,
                    nombre_usuario=nombre_usuario,
                    # Si ya era del mismo usuario, se conserva la hora
                    # original de inicio; si es nuevo, empieza ahora.
                    desde=existente.desde if existente else ahora,
                    ultimo_latido=ahora,
                    websocket=websocket,
                )
                self._bloqueos[mesa_id] = nuevo_bloqueo
                return True, nuevo_bloqueo

            return False, existente

    async def liberar(self, mesa_id: int, usuario_id: int) -> bool:
        """
        Libera una mesa, solo si quien la libera es efectivamente quien la
        tiene bloqueada (evita que un usuario libere por error la mesa de otro).
        """
        async with self._candado:
            existente = self._bloqueos.get(mesa_id)
            if existente is None or existente.usuario_id != usuario_id:
                return False
            del self._bloqueos[mesa_id]
            return True

    async def registrar_latido(self, mesa_id: int, usuario_id: int) -> bool:
        """Actualiza la marca de actividad de un bloqueo (heartbeat) para evitar que expire."""
        async with self._candado:
            existente = self._bloqueos.get(mesa_id)
            if existente is None or existente.usuario_id != usuario_id:
                return False
            existente.ultimo_latido = datetime.now(timezone.utc)
            return True

    async def obtener_estado(self) -> list[dict]:
        """Devuelve el listado completo de bloqueos activos, para enviarlo al conectarse."""
        async with self._candado:
            return [info.a_diccionario_publico() for info in self._bloqueos.values()]

    async def liberar_expirados(self) -> list[dict]:
        """
        Revisa todos los bloqueos activos y libera automáticamente los que
        llevan más tiempo sin heartbeat que TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS.
        Devuelve la lista de los bloqueos liberados, para notificar a todos.
        """
        ahora = datetime.now(timezone.utc)
        limite_segundos = configuracion.TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS
        liberados: list[dict] = []

        async with self._candado:
            for mesa_id, info in list(self._bloqueos.items()):
                segundos_inactivo = (ahora - info.ultimo_latido).total_seconds()
                if segundos_inactivo > limite_segundos:
                    liberados.append(info.a_diccionario_publico())
                    del self._bloqueos[mesa_id]

        return liberados

    async def enviar_a_usuario(self, usuario_id: int, mensaje: dict) -> None:
        """Envía un mensaje directo a todas las conexiones activas de un usuario específico."""
        conexiones = self._conexiones_por_usuario.get(usuario_id, set())
        for websocket in list(conexiones):
            try:
                await websocket.send_json(mensaje)
            except Exception:
                # Una conexión caída al momento de enviar no debe afectar a las demás
                pass

    async def difundir_a_todos(self, mensaje: dict, excluir: WebSocket | None = None) -> None:
        """Envía un mensaje a todas las conexiones activas, opcionalmente excluyendo una."""
        for websocket in list(self._todas_las_conexiones):
            if websocket is excluir:
                continue
            try:
                await websocket.send_json(mensaje)
            except Exception:
                pass


# --- Instancia única compartida por toda la aplicación (patrón singleton simple) ---
gestor_bloqueos_mesas = GestorBloqueosMesas()


async def tarea_periodica_expiracion_bloqueos() -> None:
    """
    Tarea de fondo que corre indefinidamente mientras el servidor esté
    encendido: cada pocos segundos revisa si algún bloqueo lleva demasiado
    tiempo sin heartbeat y lo libera automáticamente, avisando a todos los
    usuarios conectados para que su plano de mesas se actualice solo,
    sin que nadie tenga que recargar la página.
    """
    intervalo_revision_segundos = max(5, configuracion.TIEMPO_HEARTBEAT_SEGUNDOS // 2)
    while True:
        await asyncio.sleep(intervalo_revision_segundos)
        try:
            liberados = await gestor_bloqueos_mesas.liberar_expirados()
            for bloqueo in liberados:
                await gestor_bloqueos_mesas.difundir_a_todos(
                    {
                        "tipo": "mesa_liberada",
                        "mesa_id": bloqueo["mesa_id"],
                        "motivo": "expiro_por_inactividad",
                    }
                )
        except Exception:
            # La tarea de fondo nunca debe detenerse por un error puntual
            continue