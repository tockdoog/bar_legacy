# Ruta: backend/app/utils/configuracion_financiera.py
# Obtiene la configuración financiera global del negocio (fila única id=1) y la
# crea con valores por defecto la primera vez. Antes esta función estaba
# duplicada en routers/ventas.py y routers/finanzas.py; ahora vive en un solo lugar.
# Si dos peticiones intentan crearla a la vez (varias instancias en Vercel), la
# segunda descarta su intento y lee la que ya existe, sin afectar el resto de la transacción.

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finanzas import ConfiguracionFinanciera, TipoImpuesto

ID_CONFIGURACION_UNICA = 1


def obtener_configuracion_financiera(db: Session) -> ConfiguracionFinanciera:
    """Devuelve la configuración financiera global, creándola con valores por defecto si no existe."""
    configuracion = (
        db.query(ConfiguracionFinanciera)
        .filter(ConfiguracionFinanciera.id == ID_CONFIGURACION_UNICA)
        .first()
    )
    if configuracion is not None:
        return configuracion

    nueva = ConfiguracionFinanciera(
        id=ID_CONFIGURACION_UNICA,
        tipo_impuesto=TipoImpuesto.SIN_IMPUESTO,
        porcentaje_impuesto=0.0,
        margen_utilidad_deseado=30.0,
        margen_minimo_saludable=15.0,
    )
    try:
        # El punto de guardado (savepoint) evita deshacer el resto de la transacción si hay choque
        with db.begin_nested():
            db.add(nueva)
    except IntegrityError:
        return (
            db.query(ConfiguracionFinanciera)
            .filter(ConfiguracionFinanciera.id == ID_CONFIGURACION_UNICA)
            .one()
        )

    db.commit()
    db.refresh(nueva)
    return nueva