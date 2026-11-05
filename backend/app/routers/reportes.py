# Ruta: backend/app/routers/reportes.py
# Endpoints para consultar reportes en pantalla (JSON) y exportarlos a Excel o PDF.
# Cubre: ventas, compras, inventario, productos mas/menos vendidos, ganancias
# y actividad del escanador de codigos de barras.
#
# PERMISOS: todo este modulo requiere el permiso granular "reportes_ver" (el
# administrador siempre lo tiene por su rol; un empleado solo si el
# administrador se lo asigno desde Usuarios). Se usa un permiso propio, en
# vez de reutilizar uno de otro modulo (ej. "compras_gestionar"), porque los
# reportes exponen informacion financiera agregada de todo el negocio
# (ventas, ganancias, compras a proveedores) y el administrador debe poder
# otorgar ese acceso de forma independiente a otros permisos operativos.
#
# Seguridad aplicada:
#   - El tipo de reporte se valida contra una lista blanca antes de procesarlo.
#   - El rango de fechas se valida para que inicio no sea posterior al fin.
#   - Los datos del DataFrame se serializan con to_dict para evitar fugas de ORM.
#
# ZONA HORARIA: el rango de fechas "por defecto" (cuando el usuario no elige
# fechas, o para nombrar el archivo descargado) usa hoy_colombia() en vez de
# date.today(). date.today() toma la fecha del sistema operativo del
# contenedor (normalmente UTC dentro de Docker), lo que podia estar hasta 5
# horas adelante de la hora real de Colombia y hacia que una venta reciente
# pareciera "faltante" o con la fecha equivocada en el reporte. Ver
# app/utils/zona_horaria.py para el detalle completo del problema y la
# solucion aplicada en todo el sistema.

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.dependencies import requerir_permiso
from app.utils.exportar_excel import generar_excel
from app.utils.exportar_pdf import generar_pdf
from app.utils.generador_reportes import TIPOS_VALIDOS, construir_reporte
from app.utils.zona_horaria import hoy_colombia

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


def _resolver_rango_fechas(
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> tuple[datetime, datetime]:
    """
    Convierte las fechas recibidas a un rango datetime completo (inicio a las 00:00,
    fin a las 23:59:59). Si no se reciben fechas, usa los ultimos 30 dias por defecto,
    tomando como referencia el dia de HOY en Colombia (hoy_colombia()), no la fecha
    del sistema operativo del servidor. Lanza 400 si la fecha de inicio es
    posterior a la de fin.
    """
    # Usa hoy (en Colombia) como fin y hace 30 dias como inicio si no se reciben fechas
    fin = fecha_fin or hoy_colombia()
    inicio = fecha_inicio or (fin - timedelta(days=30))

    # Valida que el rango sea coherente
    if inicio > fin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser posterior a la fecha final.",
        )

    # Convierte a datetime con el inicio del dia y el fin del dia respectivamente.
    # Estos limites se comparan contra fechas guardadas en hora local de Colombia
    # (ver app/models/venta.py y app/utils/zona_horaria.py), por lo que representan
    # correctamente "todo el dia" en la zona horaria del negocio.
    return datetime.combine(inicio, time.min), datetime.combine(fin, time.max)


def _validar_tipo(tipo: str) -> None:
    """
    Verifica que el tipo de reporte solicitado este en la lista de tipos validos.
    Lanza 404 si el tipo no existe para no exponer informacion interna del sistema.
    """
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Tipo de reporte no valido. Usa uno de: "
                f"{', '.join(sorted(TIPOS_VALIDOS))}"
            ),
        )


@router.get("/{tipo}", summary="Consultar reporte en pantalla (JSON)")
def obtener_reporte(
    tipo: str,
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("reportes_ver")),
):
    """
    Devuelve los datos de un reporte en formato JSON listo para mostrarse en pantalla.
    El formato incluye: titulo, columnas, columnas monetarias, filas y resumen.
    """
    # Valida el tipo antes de construir el reporte (lista blanca)
    _validar_tipo(tipo)
    inicio, fin = _resolver_rango_fechas(fecha_inicio, fecha_fin)

    # Construye el reporte usando el generador compartido con Excel y PDF
    resultado = construir_reporte(tipo, db, inicio, fin)

    # Serializa el DataFrame a lista de diccionarios para la respuesta JSON
    return {
        "titulo": resultado.titulo,
        "columnas": list(resultado.dataframe.columns),
        "columnas_moneda": resultado.columnas_moneda,
        "filas": resultado.dataframe.to_dict(orient="records"),
        "resumen": resultado.resumen,
    }


@router.get("/{tipo}/excel", summary="Exportar reporte a Excel (.xlsx)")
def exportar_reporte_excel(
    tipo: str,
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("reportes_ver")),
):
    """
    Genera y descarga el reporte indicado en formato Excel (.xlsx).
    El archivo se construye en memoria (BytesIO) y se envia como stream.
    """
    _validar_tipo(tipo)
    inicio, fin = _resolver_rango_fechas(fecha_inicio, fecha_fin)

    resultado = construir_reporte(tipo, db, inicio, fin)
    archivo = generar_excel(resultado)

    # Nombre del archivo con el tipo y la fecha de generacion (Colombia) para trazabilidad
    nombre_archivo = f"reporte_{tipo}_{hoy_colombia().isoformat()}.xlsx"

    return StreamingResponse(
        archivo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/{tipo}/pdf", summary="Exportar reporte a PDF")
def exportar_reporte_pdf(
    tipo: str,
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    db: Session = Depends(obtener_db),
    usuario=Depends(requerir_permiso("reportes_ver")),
):
    """
    Genera y descarga el reporte indicado en formato PDF.
    El archivo se construye en memoria (BytesIO) y se envia como stream.
    """
    _validar_tipo(tipo)
    inicio, fin = _resolver_rango_fechas(fecha_inicio, fecha_fin)

    resultado = construir_reporte(tipo, db, inicio, fin)
    archivo = generar_pdf(resultado)

    # Nombre del archivo con el tipo y la fecha de generacion (Colombia) para trazabilidad
    nombre_archivo = f"reporte_{tipo}_{hoy_colombia().isoformat()}.pdf"

    return StreamingResponse(
        archivo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )