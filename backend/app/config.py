# Ruta: backend/app/config.py
# Configuración central de la aplicación. Lee los valores desde variables de
# entorno (en Vercel) o desde el archivo .env (en local) y los expone como un
# objeto único reutilizable en todo el backend.

import ipaddress

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Límite de Vercel para el cuerpo de una petición: 4,5 MB. Se usa 4 MiB para dejar margen.
LIMITE_IMAGEN_VERCEL_BYTES = 4 * 1024 * 1024


class Configuracion(BaseSettings):
    """
    Agrupa toda la configuración sensible de la aplicación.
    Evita tener credenciales o claves escritas directamente en el código.
    """

    # --- Entorno de ejecución: "desarrollo" o "produccion" ---
    ENTORNO: str = "desarrollo"

    # --- Seguridad de tokens JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Base de datos ---
    # Local: SQLite. Producción (Vercel): cadena de Neon con "-pooler" en el host.
    DATABASE_URL: str = "sqlite:///./negocio.db"

    # --- CORS: orígenes permitidos, separados por coma (sin "*" y sin "/" final) ---
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Datos de red local (solo desarrollo / instalación en red local) ---
    # Los usa el módulo QR para generar el enlace de vinculación de dispositivos.
    # En producción no se agregan a CORS.
    NOMBRE_HOST: str = "barlegacy.local"
    IP_SERVIDOR: str = ""

    # --- Usuario administrador inicial ---
    ADMIN_USUARIO: str = "admin"
    ADMIN_CORREO: str = "admin@negocio.com"
    ADMIN_CONTRASENA: str = "CambiarEsta123!"
    ADMIN_NOMBRE: str = "Administrador Principal"

    # --- Imágenes de productos (se guardan en la base de datos) ---
    CARPETA_IMAGENES_PRODUCTOS: str = "uploads/productos"
    TAMANO_MAXIMO_IMAGEN_BYTES: int = LIMITE_IMAGEN_VERCEL_BYTES
    LADO_MAXIMO_IMAGEN_PX: int = 800

    # --- Imágenes de las cuentas/medios de pago (QR incluidos en el despliegue) ---
    CARPETA_IMAGENES_CUENTAS_PROVEEDOR: str = "imagenes/cuentas"

    # --- Suscripción mensual y bloqueo automático (valores en pesos colombianos, COP) ---
    DIAS_SUSCRIPCION: int = 30
    CLAVE_MAESTRA_DESBLOQUEO: str
    VALOR_SUSCRIPCION_MENSUAL: int = 0
    UMBRAL_INTENTOS_DESBLOQUEO: int = 5
    MINUTOS_BLOQUEO_INTENTOS_DESBLOQUEO: int = 15

    # --- Monitoreo interno / logs ---
    CARPETA_LOGS: str = "~/logs"
    NIVEL_LOG: str = "INFO"
    LOG_MAX_BYTES: int = 5 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 10
    CLAVE_ACCESO_LOGS: str

    # --- Datos del negocio (encabezado de la factura de venta) ---
    NOMBRE_NEGOCIO: str = "Mi Negocio"
    NIT_NEGOCIO: str = ""
    DIRECCION_NEGOCIO: str = ""
    TELEFONO_NEGOCIO: str = ""

    # --- Envío de facturas por correo (si SMTP_HOST queda vacío, se deshabilita) ---
    SMTP_HOST: str = ""
    SMTP_PUERTO: int = 587
    SMTP_USUARIO: str = ""
    SMTP_CONTRASENA: str = ""
    SMTP_REMITENTE: str = ""
    SMTP_USA_TLS: bool = True

    # --- Bloqueo colaborativo de mesas (por peticiones REST) ---
    # HEARTBEAT: cada cuánto el frontend renueva el bloqueo de la mesa abierta.
    # EXPIRACION: sin renovación durante este tiempo, el bloqueo se libera solo.
    TIEMPO_HEARTBEAT_SEGUNDOS: int = 20
    TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS: int = 60

    # "forbid": una variable mal escrita en .env detiene el arranque en vez de ignorarse en silencio
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    # ------------------------------------------------------------------
    # Validaciones de campos individuales
    # ------------------------------------------------------------------

    @field_validator("SECRET_KEY")
    @classmethod
    def validar_secret_key(cls, valor: str) -> str:
        """Evita arrancar con la clave de ejemplo o con una clave demasiado corta."""
        if valor in {"", "cambiar_esta_clave_por_una_generada_de_forma_segura"}:
            raise ValueError(
                "SECRET_KEY no puede usar el valor de ejemplo. Genera una con: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if len(valor) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres para ser segura.")
        return valor

    @field_validator("CLAVE_MAESTRA_DESBLOQUEO")
    @classmethod
    def validar_clave_maestra_desbloqueo(cls, valor: str) -> str:
        """Exige una clave maestra real para el desbloqueo tras el pago mensual."""
        if not valor.strip():
            raise ValueError("CLAVE_MAESTRA_DESBLOQUEO es obligatoria.")
        if valor == "cambiar_por_una_clave_segura_de_desbloqueo":
            raise ValueError("CLAVE_MAESTRA_DESBLOQUEO no puede usar el valor de ejemplo.")
        if len(valor) < 8:
            raise ValueError("CLAVE_MAESTRA_DESBLOQUEO debe tener al menos 8 caracteres.")
        return valor

    @field_validator("CLAVE_ACCESO_LOGS")
    @classmethod
    def validar_clave_acceso_logs(cls, valor: str) -> str:
        """Exige una clave propia y no trivial para el panel de logs."""
        if valor in {"", "clave_segura_para_ver_los_logs"}:
            raise ValueError("CLAVE_ACCESO_LOGS es obligatoria y no puede usar el valor de ejemplo.")
        if len(valor) < 8:
            raise ValueError("CLAVE_ACCESO_LOGS debe tener al menos 8 caracteres.")
        return valor

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validar_cors_origins(cls, valor: str) -> str:
        """
        Normaliza los orígenes: convierte saltos de línea en comas, quita espacios,
        entradas vacías y la barra final ("https://x.app/" -> "https://x.app", ya que
        el navegador envía el origen sin barra y no coincidiría). Rechaza el comodín "*".
        """
        texto = valor.replace("\r", "").replace("\n", ",")
        partes = [parte.strip().rstrip("/") for parte in texto.split(",") if parte.strip()]
        if "*" in partes:
            raise ValueError("CORS_ORIGINS no puede contener '*': indica los dominios exactos.")
        return ",".join(partes)

    @field_validator("IP_SERVIDOR")
    @classmethod
    def validar_ip_servidor(cls, valor: str) -> str:
        """Si se define una IP, debe ser una dirección IPv4/IPv6 válida; vacía es aceptable."""
        valor = valor.strip()
        if not valor:
            return valor
        try:
            ipaddress.ip_address(valor)
        except ValueError as error:
            raise ValueError(f"IP_SERVIDOR inválida ('{valor}'): ejemplo válido 192.168.0.14.") from error
        return valor

    @field_validator("NIVEL_LOG")
    @classmethod
    def validar_nivel_log(cls, valor: str) -> str:
        """Solo permite niveles válidos del módulo logging de Python."""
        niveles_validos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if valor.upper() not in niveles_validos:
            raise ValueError(f"NIVEL_LOG debe ser uno de: {', '.join(sorted(niveles_validos))}")
        return valor.upper()

    @field_validator("SMTP_PUERTO")
    @classmethod
    def validar_smtp_puerto(cls, valor: int) -> int:
        """El puerto SMTP debe estar en el rango TCP válido."""
        if not (1 <= valor <= 65535):
            raise ValueError("SMTP_PUERTO debe estar entre 1 y 65535.")
        return valor

    @field_validator("TAMANO_MAXIMO_IMAGEN_BYTES")
    @classmethod
    def validar_tamano_imagen(cls, valor: int) -> int:
        """Vercel rechaza cuerpos de más de 4,5 MB: se limita a 4 MiB para evitar fallos sin mensaje."""
        if not (0 < valor <= LIMITE_IMAGEN_VERCEL_BYTES):
            raise ValueError(
                "TAMANO_MAXIMO_IMAGEN_BYTES debe estar entre 1 y 4194304 (4 MB): "
                "Vercel no admite peticiones más grandes."
            )
        return valor

    @field_validator("TIEMPO_HEARTBEAT_SEGUNDOS")
    @classmethod
    def validar_tiempo_heartbeat(cls, valor: int) -> int:
        """El latido no puede ser tan corto que sature la base de datos."""
        if valor < 5:
            raise ValueError("TIEMPO_HEARTBEAT_SEGUNDOS debe ser de al menos 5 segundos.")
        return valor

    # ------------------------------------------------------------------
    # Validaciones cruzadas entre varios campos
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def validar_credenciales_en_produccion(self) -> "Configuracion":
        """En producción, el administrador inicial no puede usar la contraseña de ejemplo ni una corta."""
        if self.es_produccion:
            if self.ADMIN_CONTRASENA == "CambiarEsta123!":
                raise ValueError("ADMIN_CONTRASENA no puede ser el valor de ejemplo en producción.")
            if len(self.ADMIN_CONTRASENA) < 10:
                raise ValueError("ADMIN_CONTRASENA debe tener al menos 10 caracteres en producción.")
        return self

    @model_validator(mode="after")
    def validar_base_datos_en_produccion(self) -> "Configuracion":
        """En producción SQLite no sirve (el disco de Vercel es de solo lectura): se exige PostgreSQL."""
        if self.es_produccion and self.DATABASE_URL.strip().startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL apunta a SQLite con ENTORNO=produccion. "
                "Usa la cadena de conexión de Neon (con '-pooler' en el host)."
            )
        return self

    @model_validator(mode="after")
    def validar_tiempos_bloqueo_mesas(self) -> "Configuracion":
        """La expiración debe ser mayor al doble del latido, para tolerar un latido perdido."""
        if self.TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS <= self.TIEMPO_HEARTBEAT_SEGUNDOS * 2:
            raise ValueError(
                "TIEMPO_EXPIRACION_BLOQUEO_SEGUNDOS debe ser mayor al doble de TIEMPO_HEARTBEAT_SEGUNDOS."
            )
        return self

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------

    @property
    def lista_origenes_cors(self) -> list[str]:
        """
        Lista final de orígenes permitidos para CORS.
        - Producción: SOLO los definidos en CORS_ORIGINS (superficie mínima).
        - Desarrollo: además el hostname local y la IP del servidor (acceso desde celulares en red local).
        """
        origenes = [origen for origen in self.CORS_ORIGINS.split(",") if origen]

        if not self.es_produccion:
            origenes.append(f"https://{self.NOMBRE_HOST}:5443")
            if self.IP_SERVIDOR:
                origenes.append(f"https://{self.IP_SERVIDOR}:5443")

        # Elimina duplicados conservando el orden
        return list(dict.fromkeys(origenes))

    @property
    def es_produccion(self) -> bool:
        """Indica si el sistema corre en entorno de producción."""
        return self.ENTORNO.lower() == "produccion"


# Instancia única de configuración que se importa en el resto del proyecto
configuracion = Configuracion()