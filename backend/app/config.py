# Ruta: backend/app/config.py
# Configuración central de la aplicación. Lee los valores desde el archivo .env
# y los expone como un objeto único reutilizable en todo el backend.

import ipaddress

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """
    Clase que agrupa toda la configuración sensible de la aplicación.
    Evita tener credenciales o claves escritas directamente en el código.
    """

    # --- Entorno de ejecución: "desarrollo" o "produccion" ---
    ENTORNO: str = "desarrollo"

    # --- Seguridad de tokens JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Base de datos ---
    # Este valor por defecto ("./negocio.db" en la carpeta de trabajo actual)
    # se usa SOLO si corres el backend fuera de Docker (ej. en desarrollo
    # local con "uvicorn app.main:app --reload"). Dentro de Docker, este
    # valor se sobreescribe siempre desde docker/docker-compose.yml
    # (servicio "backend", variable de entorno DATABASE_URL), apuntando a
    # "./data/negocio.db", que dentro del contenedor es /app/data: la
    # carpeta montada como volumen nombrado "db_backend" (ver
    # docker-compose.yml para el porqué de usar un volumen nombrado en vez
    # de un archivo suelto montado desde el host).
    DATABASE_URL: str = "sqlite:///./negocio.db"

    # --- CORS: orígenes permitidos para consumir la API, definidos a mano ---
    # IMPORTANTE: ya NO es necesario agregar aquí la IP local de la red ni
    # "localhost". El sistema se identifica SIEMPRE con el hostname fijo
    # "barlegacy.local", inyectado automáticamente en cada arranque a
    # través de la variable NOMBRE_HOST (ver propiedad "lista_origenes_cors"
    # más abajo). Esto evita que el instalador tenga que reescribir este
    # archivo y lo protege de quedar corrupto.
    CORS_ORIGINS: str = "https://barlegacy.local:5443"

    # --- Hostname fijo del sistema, inyectado por docker-compose ---
    # Se recibe como variable de entorno del contenedor (ver
    # docker/docker-compose.yml, servicio "backend") y NO se define en
    # backend/.env. Por defecto es "barlegacy.local": es la dirección que
    # deben usar las COMPUTADORAS (se puede escribir a mano y recordar).
    NOMBRE_HOST: str = "barlegacy.local"

    # --- IP local del servidor en la red, inyectada por docker-compose ---
    # Es OPCIONAL y se usa únicamente para dos cosas:
    #   1. Sumarla como origen adicional válido para CORS y para la
    #      validación de la cabecera Origin del WebSocket de mesas (ver
    #      "lista_origenes_cors" más abajo).
    #   2. Que el código QR de vinculación de dispositivos
    #      (backend/QR/router.py) apunte a esta IP en vez del hostname.
    # Esto existe porque los CELULARES (Android/iOS) no pueden resolver
    # "barlegacy.local" sin instalar una app externa para editar su
    # archivo hosts, mientras que una dirección IP no necesita ninguna
    # resolución de nombres: funciona de inmediato al escanear el QR.
    # Se detecta automáticamente en cada instalación (ver
    # execution/windows/instalar.bat) y puede quedar vacía si no se pudo
    # detectar; en ese caso el QR informa el problema en vez de fallar.
    IP_SERVIDOR: str = ""

    # --- Usuario administrador inicial ---
    ADMIN_USUARIO: str = "admin"
    ADMIN_CORREO: str = "admin@negocio.com"
    ADMIN_CONTRASENA: str = "CambiarEsta123!"
    ADMIN_NOMBRE: str = "Administrador Principal"

    # --- Imágenes de productos ---
    CARPETA_IMAGENES_PRODUCTOS: str = "uploads/productos"
    TAMANO_MAXIMO_IMAGEN_BYTES: int = 5 * 1024 * 1024
    LADO_MAXIMO_IMAGEN_PX: int = 800

    # --- Imágenes de las cuentas/medios de pago (QR de Nequi, Bancolombia, etc.) ---
    # Comparte los mismos límites de tamaño y resolución que las imágenes de
    # productos (TAMANO_MAXIMO_IMAGEN_BYTES y LADO_MAXIMO_IMAGEN_PX), solo
    # cambia la carpeta de destino.
    CARPETA_IMAGENES_CUENTAS_PROVEEDOR: str = "imagenes/cuentas"

    # --- Módulo de suscripción y bloqueo automático por pago mensual (valores en COP) ---
    DIAS_SUSCRIPCION: int = 30
    CLAVE_MAESTRA_DESBLOQUEO: str
    VALOR_SUSCRIPCION_MENSUAL: int = 0
    UMBRAL_INTENTOS_DESBLOQUEO: int = 5
    MINUTOS_BLOQUEO_INTENTOS_DESBLOQUEO: int = 15

    # --- Módulo de monitoreo interno / logs (carpeta ~/logs) ---
    CARPETA_LOGS: str = "~/logs"
    NIVEL_LOG: str = "INFO"
    LOG_MAX_BYTES: int = 5 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 10
    CLAVE_ACCESO_LOGS: str

    # --- Datos del negocio, usados en el encabezado de la factura de venta ---
    # No representan ningún nicho: son los datos de identificación de
    # cualquier negocio (nombre comercial, NIT, dirección y teléfono).
    NOMBRE_NEGOCIO: str = "Mi Negocio"
    NIT_NEGOCIO: str = ""
    DIRECCION_NEGOCIO: str = ""
    TELEFONO_NEGOCIO: str = ""

    # --- Envío de facturas por correo electrónico (servidor SMTP) ---
    # Si SMTP_HOST queda vacío, el envío de facturas por correo simplemente
    # se deshabilita (el resto del sistema sigue funcionando con normalidad).
    SMTP_HOST: str = ""
    SMTP_PUERTO: int = 587
    SMTP_USUARIO: str = ""
    SMTP_CONTRASENA: str = ""
    SMTP_REMITENTE: str = ""
    SMTP_USA_TLS: bool = True

    # --- Bloqueo colaborativo de mesas en tiempo real (WebSockets) ---
    # TIEMPO_HEARTBEAT_SEGUNDOS: cada cuánto el frontend debe avisar "sigo
    # aquí trabajando en esta mesa" mientras la tiene abierta.
    # TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS: si no llega ningún heartbeat
    # durante este tiempo (ej. se cerró el navegador de golpe, se fue la
    # luz, perdió la conexión), el bloqueo se libera automáticamente para
    # que otro mesero pueda tomar la mesa sin quedar bloqueada para siempre.
    TIEMPO_HEARTBEAT_SEGUNDOS: int = 20
    TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("SECRET_KEY")
    @classmethod
    def validar_secret_key(cls, valor: str) -> str:
        """Evita que el sistema arranque con la clave de ejemplo o una clave demasiado corta."""
        valores_inseguros = {"", "cambiar_esta_clave_por_una_generada_de_forma_segura"}
        if valor in valores_inseguros:
            raise ValueError(
                "SECRET_KEY no puede usar el valor de ejemplo. "
                "Genera una clave segura con: openssl rand -hex 32"
            )
        if len(valor) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres para ser segura.")
        return valor

    @field_validator("CLAVE_MAESTRA_DESBLOQUEO")
    @classmethod
    def validar_clave_maestra_desbloqueo(cls, valor: str) -> str:
        """Impide que el sistema arranque sin una clave maestra de desbloqueo real."""
        if not valor or valor.strip() == "":
            raise ValueError(
                "CLAVE_MAESTRA_DESBLOQUEO es obligatoria: es la contraseña que "
                "desbloquea el sistema tras el pago mensual."
            )
        if len(valor) < 8:
            raise ValueError("CLAVE_MAESTRA_DESBLOQUEO debe tener al menos 8 caracteres.")
        return valor

    @field_validator("CLAVE_ACCESO_LOGS")
    @classmethod
    def validar_clave_acceso_logs(cls, valor: str) -> str:
        """
        Impide que el sistema arranque sin definir la clave del panel de logs,
        o con una demasiado corta y fácil de adivinar por fuerza bruta.
        """
        valores_inseguros = {"", "clave_segura_para_ver_los_logs"}
        if valor in valores_inseguros:
            raise ValueError(
                "CLAVE_ACCESO_LOGS es obligatoria y no puede usar el valor de ejemplo: "
                "define una clave propia en el archivo .env."
            )
        if len(valor) < 8:
            raise ValueError("CLAVE_ACCESO_LOGS debe tener al menos 8 caracteres.")
        return valor

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validar_cors_origins(cls, valor: str) -> str:
        """
        Normaliza y valida los orígenes de CORS definidos a mano en .env:
        - Convierte saltos de línea accidentales en comas (defensa adicional
          por si el archivo se llegara a editar mal manualmente).
        - Elimina espacios en blanco y entradas vacías.
        - Rechaza el uso del comodín "*".
        Esta limpieza es una segunda capa de seguridad: la reparación
        principal de un .env corrupto la hace el instalador antes de que
        Docker Compose intente leer el archivo.
        """
        valor_normalizado = valor.replace("\r", "").replace("\n", ",")
        partes = [parte.strip() for parte in valor_normalizado.split(",") if parte.strip()]
        if any(parte == "*" for parte in partes):
            raise ValueError(
                "CORS_ORIGINS no puede contener '*'. Especifica los dominios exactos "
                "permitidos, separados por coma (ej: https://barlegacy.local:5443)."
            )
        return ",".join(partes)

    @field_validator("IP_SERVIDOR")
    @classmethod
    def validar_ip_servidor(cls, valor: str) -> str:
        """
        Si se recibió una IP (detectada por el instalador), valida que sea
        una dirección IPv4/IPv6 real y bien formada. Si viene vacía, se deja
        pasar tal cual: el QR simplemente informará que falta configurarla.
        """
        valor = valor.strip()
        if not valor:
            return valor
        try:
            ipaddress.ip_address(valor)
        except ValueError as error:
            raise ValueError(
                f"IP_SERVIDOR tiene un valor inválido ('{valor}'): debe ser una "
                "dirección IP real, ej. 192.168.0.14."
            ) from error
        return valor

    @field_validator("NIVEL_LOG")
    @classmethod
    def validar_nivel_log(cls, valor: str) -> str:
        """Solo permite los niveles válidos del módulo logging de Python."""
        niveles_validos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        valor_normalizado = valor.upper()
        if valor_normalizado not in niveles_validos:
            raise ValueError(f"NIVEL_LOG debe ser uno de: {', '.join(niveles_validos)}")
        return valor_normalizado

    @field_validator("SMTP_PUERTO")
    @classmethod
    def validar_smtp_puerto(cls, valor: int) -> int:
        """Valida que el puerto SMTP esté en un rango de puertos TCP válido."""
        if not (1 <= valor <= 65535):
            raise ValueError("SMTP_PUERTO debe estar entre 1 y 65535.")
        return valor

    @field_validator("TIEMPO_HEARTBEAT_SEGUNDOS")
    @classmethod
    def validar_tiempo_heartbeat(cls, valor: int) -> int:
        """El heartbeat debe ser un valor razonable: ni tan corto que sature la red, ni tan largo que sea inútil."""
        if valor < 5:
            raise ValueError("TIEMPO_HEARTBEAT_SEGUNDOS debe ser de al menos 5 segundos.")
        return valor

    @model_validator(mode="after")
    def validar_credenciales_en_produccion(self) -> "Configuracion":
        """
        En entorno de producción, impide que el sistema arranque si el usuario
        administrador inicial sigue con valores de ejemplo.
        """
        if self.es_produccion and self.ADMIN_CONTRASENA == "CambiarEsta123!":
            raise ValueError(
                "ADMIN_CONTRASENA no puede ser el valor de ejemplo cuando ENTORNO=produccion. "
                "Define una contraseña segura en el archivo .env."
            )
        return self

    @model_validator(mode="after")
    def validar_tiempos_bloqueo_mesas(self) -> "Configuracion":
        """
        El tiempo de expiración del bloqueo debe ser mayor al del heartbeat
        (con margen), o los bloqueos se liberarían solos incluso con el
        usuario activo trabajando normalmente en la mesa.
        """
        if self.TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS <= self.TIEMPO_HEARTBEAT_SEGUNDOS * 2:
            raise ValueError(
                "TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS debe ser al menos el doble de "
                "TIEMPO_HEARTBEAT_SEGUNDOS, para tolerar un heartbeat perdido por la red."
            )
        return self

    @property
    def lista_origenes_cors(self) -> list[str]:
        """
        Devuelve la lista final de orígenes permitidos para CORS, combinando:
        1. Los orígenes fijos definidos a mano en CORS_ORIGINS (.env).
        2. El origen HTTPS del hostname fijo del sistema (NOMBRE_HOST),
           inyectado automáticamente en cada arranque del contenedor
           (por defecto "https://barlegacy.local:5443"), usado por las
           computadoras.
        3. El origen HTTPS de la IP local del servidor (IP_SERVIDOR), si fue
           detectada, usado por los celulares que acceden escaneando el QR.
        La combinación ocurre en memoria (Python), nunca reescribiendo el
        archivo .env, por lo que backend/.env no se corrompe si el hostname
        o la IP cambiaran. Esta misma lista también la usa el WebSocket de
        mesas en tiempo real para validar la cabecera Origin.
        """
        origenes_manuales = [origen.strip() for origen in self.CORS_ORIGINS.split(",") if origen.strip()]
        origen_hostname_fijo = f"https://{self.NOMBRE_HOST}:5443"

        origenes_combinados = origenes_manuales + [origen_hostname_fijo]
        if self.IP_SERVIDOR:
            origenes_combinados.append(f"https://{self.IP_SERVIDOR}:5443")

        # Elimina duplicados conservando el orden
        vistos: set[str] = set()
        origenes_unicos: list[str] = []
        for origen in origenes_combinados:
            if origen not in vistos:
                vistos.add(origen)
                origenes_unicos.append(origen)
        return origenes_unicos

    @property
    def es_produccion(self) -> bool:
        """Indica si el sistema está corriendo en entorno de producción."""
        return self.ENTORNO.lower() == "produccion"


# Instancia única de configuración que se importa en el resto del proyecto
configuracion = Configuracion()