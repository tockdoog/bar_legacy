# Ruta: backend/app/logs/schemas.py
# Esquemas de validación y respuesta usados por el módulo de monitoreo de logs.

from enum import Enum

from pydantic import BaseModel, Field


class CategoriaLog(str, Enum):
    """
    Únicas categorías de log permitidas. Al usar un Enum en el endpoint,
    FastAPI rechaza automáticamente cualquier valor distinto, lo que impide
    ataques de "path traversal" (ej. intentar leer ../../.env).
    """
    ACCESOS = "accesos"
    SEGURIDAD = "seguridad"
    ERRORES = "errores"
    SISTEMA = "sistema"
    # Acciones sensibles de negocio: cambios de precios, eliminaciones,
    # apertura/cierre de caja, devoluciones, etc. Aplica a cualquier tipo de
    # negocio, sin depender de un rubro específico.
    NEGOCIO = "negocio"


class LineaLog(BaseModel):
    """
    Representa una línea individual ya interpretada de un archivo de log,
    incluyendo (cuando aplica) la severidad detectada y una recomendación
    puntual de qué hacer frente a ese evento.
    """
    fecha_hora: str
    nivel: str
    mensaje: str
    severidad: str | None = None
    recomendacion: str | None = None


class ResumenLogs(BaseModel):
    """Resumen general usado en el panel de monitoreo (conteo por categoría)."""
    categoria: CategoriaLog
    total_lineas: int
    peso_archivo_kb: float
    ultima_modificacion: str | None


class VerificacionClaveLogs(BaseModel):
    """Datos enviados por el administrador para desbloquear el panel de logs."""
    clave: str = Field(min_length=1, max_length=200)


class AlertaDetectada(BaseModel):
    """
    Alerta agrupada del "Centro de Alertas": agrupa varias líneas repetidas
    del mismo tipo de problema en un solo resumen con su recomendación.
    """
    categoria: CategoriaLog
    titulo: str
    severidad: str
    recomendacion: str
    ocurrencias: int
    ultima_fecha_hora: str