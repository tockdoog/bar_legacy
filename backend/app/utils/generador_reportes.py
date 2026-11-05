# Ruta: backend/app/utils/generador_reportes.py
# Construye los datos de cada tipo de reporte usando Pandas, a partir de la
# informacion guardada en la base de datos. Esta capa es compartida por la
# vista en pantalla (JSON) y por las exportaciones a Excel y PDF.
# Incluye el reporte de actividad del escanador de codigos de barras, el
# desglose de facturas partidas (varios metodos de pago) en el reporte de
# ventas, y el reporte de ventas anuladas (que muestra los productos
# anulados, quien anulo y el motivo).

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.models.compra import Compra, DetalleCompra
from app.models.producto import Producto
from app.models.venta import (
    Venta,
    DetalleVenta,
    EstadoVenta,
    PagoVentaDetalle,
    ETIQUETAS_METODO_PAGO,
)

# Importacion condicional del modelo de escaneos para no romper si la tabla
# aun no existe en instalaciones antiguas (se crea con create_all al iniciar)
try:
    from escaner.models import EscaneoLog
    ESCANEOS_DISPONIBLE = True
except ImportError:
    ESCANEOS_DISPONIBLE = False

# Conjunto de tipos de reporte disponibles en el sistema
# Se usa para validar el tipo antes de construirlo
TIPOS_VALIDOS = {
    "ventas",
    "ventas-anuladas",
    "compras",
    "inventario",
    "mas-vendidos",
    "menos-vendidos",
    "ganancias",
    "escaneos",
}

# Titulos legibles en espanol para cada tipo de reporte
# Se usan en la vista en pantalla, en el PDF y en el Excel
TITULOS_REPORTE = {
    "ventas": "Reporte de ventas",
    "ventas-anuladas": "Ventas anuladas",
    "compras": "Reporte de compras",
    "inventario": "Reporte de inventario",
    "mas-vendidos": "Productos mas vendidos",
    "menos-vendidos": "Productos menos vendidos",
    "ganancias": "Reporte de ganancias",
    "escaneos": "Actividad del escanador de codigos de barras",
}


@dataclass
class ResultadoReporte:
    """
    Estructura comun que devuelve cualquier reporte generado por el sistema.
    Contiene el titulo, el DataFrame con los datos, las columnas monetarias
    (para formateo en COP) y el resumen de totales generales.
    """
    titulo: str
    dataframe: pd.DataFrame
    columnas_moneda: list[str] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)


def construir_reporte(
    tipo: str,
    db: Session,
    fecha_inicio: datetime,
    fecha_fin: datetime,
) -> ResultadoReporte:
    """
    Punto de entrada unico para construir cualquier tipo de reporte.
    Delega a la funcion especializada segun el tipo recibido.
    """
    if tipo == "ventas":
        return _reporte_ventas(db, fecha_inicio, fecha_fin)
    if tipo == "ventas-anuladas":
        return _reporte_ventas_anuladas(db, fecha_inicio, fecha_fin)
    if tipo == "compras":
        return _reporte_compras(db, fecha_inicio, fecha_fin)
    if tipo == "inventario":
        return _reporte_inventario(db)
    if tipo == "mas-vendidos":
        return _reporte_productos_vendidos(db, fecha_inicio, fecha_fin, ascendente=False)
    if tipo == "menos-vendidos":
        return _reporte_productos_vendidos(db, fecha_inicio, fecha_fin, ascendente=True)
    if tipo == "ganancias":
        return _reporte_ganancias(db, fecha_inicio, fecha_fin)
    if tipo == "escaneos":
        return _reporte_escaneos(db, fecha_inicio, fecha_fin)

    raise ValueError(f"Tipo de reporte no soportado: {tipo}")


def _etiqueta_metodo_pago_venta(venta: Venta) -> str:
    """
    Construye el texto del método de pago de una venta para mostrar en el
    reporte. Si se cobró con un solo método, devuelve su etiqueta (ej.
    "Efectivo"). Si fue una factura partida (dos o más métodos, marcada como
    MIXTO), arma el desglose exacto, ej. "Pago mixto (Efectivo $10.000 + Nequi $5.000)".
    """
    if not venta.metodo_pago:
        return "—"
    if len(venta.pagos) <= 1:
        return ETIQUETAS_METODO_PAGO.get(venta.metodo_pago, "—")

    desglose = " + ".join(
        f"{ETIQUETAS_METODO_PAGO.get(pago.metodo_pago, pago.metodo_pago)} "
        f"${pago.monto:,.0f}".replace(",", ".")
        for pago in venta.pagos
    )
    return f"Pago mixto ({desglose})"


def _reporte_ventas(db: Session, inicio: datetime, fin: datetime) -> ResultadoReporte:
    """
    Lista las ventas cobradas en el rango de fechas indicado.
    Incluye el metodo de pago (o el desglose completo si fue una factura
    partida) utilizado por el cliente en cada cobro, para trazabilidad
    completa en pantalla, Excel y PDF.
    """
    # Trae las ventas con sus relaciones cargadas en una sola consulta
    ventas = (
        db.query(Venta)
        .options(joinedload(Venta.mesa), joinedload(Venta.usuario), joinedload(Venta.pagos))
        .filter(
            Venta.estado == EstadoVenta.PAGADA,
            Venta.fecha_pago >= inicio,
            Venta.fecha_pago <= fin,
        )
        .order_by(Venta.fecha_pago)
        .all()
    )

    # Construye una fila por venta con los campos relevantes para el reporte,
    # incluyendo el metodo de pago (o desglose de factura partida)
    filas = [
        {
            "Fecha": v.fecha_pago.strftime("%Y-%m-%d %H:%M"),
            "Mesa": f"Mesa {v.mesa.numero}" if v.mesa_id and v.mesa else "Venta rapida",
            "Vendedor": v.usuario.nombre_completo if v.usuario else "—",
            "Método de pago": _etiqueta_metodo_pago_venta(v),
            "Total": v.total,
            "Cambio": v.cambio or 0,
        }
        for v in ventas
    ]
    df = pd.DataFrame(
        filas,
        columns=["Fecha", "Mesa", "Vendedor", "Método de pago", "Total", "Cambio"],
    )

    # Resumen de totales para las tarjetas de encabezado del reporte
    resumen = {
        "Numero de ventas": len(df),
        "Monto total vendido": round(df["Total"].sum(), 2) if not df.empty else 0,
    }

    # Desglose adicional: monto vendido por cada metodo de pago, calculado
    # directamente sobre la tabla de pagos (pagos_venta) y no sobre la
    # columna "resumen" de la venta, para que una factura partida reparta
    # correctamente su monto entre cada método (ej. cuanto entro en
    # efectivo vs Nequi, aunque una misma venta haya usado ambos).
    pagos_del_periodo = (
        db.query(PagoVentaDetalle)
        .join(Venta)
        .filter(
            Venta.estado == EstadoVenta.PAGADA,
            Venta.fecha_pago >= inicio,
            Venta.fecha_pago <= fin,
        )
        .all()
    )
    if pagos_del_periodo:
        totales_por_metodo: dict[str, float] = {}
        for pago in pagos_del_periodo:
            etiqueta = ETIQUETAS_METODO_PAGO.get(pago.metodo_pago, str(pago.metodo_pago))
            totales_por_metodo[etiqueta] = totales_por_metodo.get(etiqueta, 0) + pago.monto
        for etiqueta, monto in totales_por_metodo.items():
            resumen[f"Total en {etiqueta}"] = round(monto, 2)

    return ResultadoReporte(
        TITULOS_REPORTE["ventas"],
        df,
        columnas_moneda=["Total", "Cambio"],
        resumen=resumen,
    )


def _reporte_ventas_anuladas(db: Session, inicio: datetime, fin: datetime) -> ResultadoReporte:
    """
    Lista las ventas anuladas en el rango de fechas indicado (filtrando por
    fecha de ANULACION, no de cobro), mostrando exactamente qué productos se
    anularon, cuándo, quién lo hizo y el motivo. Los productos se muestran
    como texto resumido (ej. "2x Cerveza, 1x Papas") porque una anulación
    aplica a la venta completa, no a productos individuales sueltos.
    """
    ventas = (
        db.query(Venta)
        .options(
            joinedload(Venta.detalles).joinedload(DetalleVenta.producto),
            joinedload(Venta.mesa),
            joinedload(Venta.usuario),
            joinedload(Venta.usuario_anulacion),
        )
        .filter(
            Venta.estado == EstadoVenta.ANULADA,
            Venta.fecha_anulacion >= inicio,
            Venta.fecha_anulacion <= fin,
        )
        .order_by(Venta.fecha_anulacion.desc())
        .all()
    )

    filas = [
        {
            "Venta": f"#{v.id}",
            "Mesa": f"Mesa {v.mesa.numero}" if v.mesa_id and v.mesa else "Venta rapida",
            "Vendedor original": v.usuario.nombre_completo if v.usuario else "—",
            "Fecha de anulación": v.fecha_anulacion.strftime("%Y-%m-%d %H:%M") if v.fecha_anulacion else "—",
            "Anulado por": v.usuario_anulacion.nombre_completo if v.usuario_anulacion else "—",
            "Productos anulados": (
                ", ".join(f"{d.cantidad}x {d.producto.nombre}" for d in v.detalles if d.producto)
                or "—"
            ),
            "Motivo": v.motivo_anulacion or "—",
            "Total anulado": v.total,
        }
        for v in ventas
    ]
    df = pd.DataFrame(
        filas,
        columns=[
            "Venta", "Mesa", "Vendedor original", "Fecha de anulación",
            "Anulado por", "Productos anulados", "Motivo", "Total anulado",
        ],
    )

    resumen = {
        "Ventas anuladas": len(df),
        "Monto total anulado": round(df["Total anulado"].sum(), 2) if not df.empty else 0,
    }
    return ResultadoReporte(
        TITULOS_REPORTE["ventas-anuladas"],
        df,
        columnas_moneda=["Total anulado"],
        resumen=resumen,
    )


def _reporte_compras(db: Session, inicio: datetime, fin: datetime) -> ResultadoReporte:
    """
    Lista las compras a proveedores registradas en el rango de fechas indicado.
    Incluye el desglose por producto con codigo de barras para trazabilidad.
    """
    # Trae los detalles de compra con producto y compra cargados
    detalles = (
        db.query(DetalleCompra)
        .join(Compra)
        .options(
            joinedload(DetalleCompra.compra).joinedload(Compra.proveedor),
            joinedload(DetalleCompra.producto),
        )
        .filter(Compra.fecha >= inicio, Compra.fecha <= fin)
        .order_by(Compra.fecha)
        .all()
    )

    # Construye una fila por producto dentro de cada compra
    filas = [
        {
            "Fecha": d.compra.fecha.strftime("%Y-%m-%d %H:%M"),
            "Proveedor": d.compra.proveedor.nombre if d.compra.proveedor else "—",
            "Producto": d.producto.nombre if d.producto else "—",
            "Codigo de barras": d.producto.codigo_barras or "—" if d.producto else "—",
            "Cantidad": d.cantidad,
            "Costo unitario": d.costo_unitario,
            "Subtotal": d.subtotal,
        }
        for d in detalles
    ]
    df = pd.DataFrame(
        filas,
        columns=[
            "Fecha", "Proveedor", "Producto", "Codigo de barras",
            "Cantidad", "Costo unitario", "Subtotal",
        ],
    )

    # Resumen: numero de compras unicas y monto total gastado
    compras_ids = {d.compra_id for d in detalles}
    resumen = {
        "Numero de compras": len(compras_ids),
        "Monto total comprado": round(df["Subtotal"].sum(), 2) if not df.empty else 0,
    }
    return ResultadoReporte(
        TITULOS_REPORTE["compras"],
        df,
        columnas_moneda=["Costo unitario", "Subtotal"],
        resumen=resumen,
    )


def _reporte_inventario(db: Session) -> ResultadoReporte:
    """
    Muestra el estado actual de todo el inventario activo con su valor estimado.
    Incluye el codigo de barras de cada producto para identificacion rapida.
    """
    # Trae todos los productos activos con su categoria
    productos = (
        db.query(Producto)
        .options(joinedload(Producto.categoria))
        .filter(Producto.activo.is_(True))
        .order_by(Producto.nombre)
        .all()
    )

    # Construye una fila por producto con todos los campos del inventario
    filas = [
        {
            "Producto": p.nombre,
            "Codigo de barras": p.codigo_barras or "—",
            "Categoria": p.categoria.nombre if p.categoria else "—",
            "Presentacion": p.presentacion,
            "Stock actual": p.stock_actual,
            "Stock minimo": p.stock_minimo,
            "Precio compra": p.precio_compra,
            "Precio venta": p.precio_venta,
            "Valor en inventario": round(p.stock_actual * p.precio_compra, 2),
        }
        for p in productos
    ]
    df = pd.DataFrame(
        filas,
        columns=[
            "Producto", "Codigo de barras", "Categoria", "Presentacion",
            "Stock actual", "Stock minimo", "Precio compra", "Precio venta",
            "Valor en inventario",
        ],
    )

    # Calcula cuantos productos tienen stock en o por debajo del minimo (alertas)
    productos_bajo_stock = (
        int((df["Stock actual"] <= df["Stock minimo"]).sum())
        if not df.empty
        else 0
    )

    resumen = {
        "Productos activos": len(df),
        "Valor total del inventario": round(df["Valor en inventario"].sum(), 2) if not df.empty else 0,
        "Productos con stock bajo": productos_bajo_stock,
    }
    return ResultadoReporte(
        TITULOS_REPORTE["inventario"],
        df,
        columnas_moneda=["Precio compra", "Precio venta", "Valor en inventario"],
        resumen=resumen,
    )


def _reporte_productos_vendidos(
    db: Session,
    inicio: datetime,
    fin: datetime,
    ascendente: bool,
) -> ResultadoReporte:
    """
    Agrupa los productos vendidos en el rango de fechas y los ordena por cantidad.
    ascendente=False: mas vendidos primero.
    ascendente=True: menos vendidos primero.
    Incluye el codigo de barras para identificacion rapida en el reporte impreso.
    """
    # Trae los detalles de venta con el producto cargado
    detalles = (
        db.query(DetalleVenta)
        .join(Venta)
        .options(joinedload(DetalleVenta.producto))
        .filter(
            Venta.estado == EstadoVenta.PAGADA,
            Venta.fecha_pago >= inicio,
            Venta.fecha_pago <= fin,
        )
        .all()
    )

    # Construye una fila por detalle con nombre y codigo del producto
    filas = [
        {
            "Producto": d.producto.nombre if d.producto else "—",
            "Codigo de barras": d.producto.codigo_barras or "—" if d.producto else "—",
            "Cantidad vendida": d.cantidad,
            "Total vendido": d.subtotal,
        }
        for d in detalles
    ]
    df = pd.DataFrame(
        filas,
        columns=["Producto", "Codigo de barras", "Cantidad vendida", "Total vendido"],
    )

    # Agrupa por producto y ordena. Se mantiene el codigo del primer registro del grupo.
    if not df.empty:
        df = (
            df.groupby(["Producto", "Codigo de barras"], as_index=False)
            .sum()
            .sort_values(by="Cantidad vendida", ascending=ascendente)
            .head(15)
            .reset_index(drop=True)
        )

    tipo_titulo = "mas-vendidos" if not ascendente else "menos-vendidos"
    resumen = {
        "Productos distintos vendidos": len(df),
        "Unidades totales": int(df["Cantidad vendida"].sum()) if not df.empty else 0,
    }
    return ResultadoReporte(
        TITULOS_REPORTE[tipo_titulo],
        df,
        columnas_moneda=["Total vendido"],
        resumen=resumen,
    )


def _reporte_ganancias(db: Session, inicio: datetime, fin: datetime) -> ResultadoReporte:
    """
    Calcula dia por dia el total vendido, el costo de lo vendido y la ganancia estimada.
    Incluye el codigo de barras del producto para trazabilidad en el detalle.
    """
    # Trae los detalles de venta con la venta cargada
    detalles = (
        db.query(DetalleVenta)
        .join(Venta)
        .options(
            joinedload(DetalleVenta.venta),
            joinedload(DetalleVenta.producto),
        )
        .filter(
            Venta.estado == EstadoVenta.PAGADA,
            Venta.fecha_pago >= inicio,
            Venta.fecha_pago <= fin,
        )
        .all()
    )

    # Construye una fila por detalle con fecha, montos y codigo del producto
    filas = [
        {
            "Fecha": d.venta.fecha_pago.strftime("%Y-%m-%d"),
            "Ventas": d.subtotal,
            "Costo": round(d.cantidad * d.precio_compra_unitario, 2),
            "Ganancia": d.ganancia,
        }
        for d in detalles
    ]
    df = pd.DataFrame(filas, columns=["Fecha", "Ventas", "Costo", "Ganancia"])

    # Agrupa por fecha para obtener totales diarios
    if not df.empty:
        df = (
            df.groupby("Fecha", as_index=False)
            .sum()
            .sort_values(by="Fecha")
            .reset_index(drop=True)
        )

    resumen = {
        "Ventas totales": round(df["Ventas"].sum(), 2) if not df.empty else 0,
        "Costo total": round(df["Costo"].sum(), 2) if not df.empty else 0,
        "Ganancia estimada": round(df["Ganancia"].sum(), 2) if not df.empty else 0,
    }
    return ResultadoReporte(
        TITULOS_REPORTE["ganancias"],
        df,
        columnas_moneda=["Ventas", "Costo", "Ganancia"],
        resumen=resumen,
    )


def _reporte_escaneos(db: Session, inicio: datetime, fin: datetime) -> ResultadoReporte:
    """
    Muestra la actividad del escanador de codigos de barras en el periodo indicado.
    Incluye: fecha, usuario, modulo de origen, codigo de barras (cuando fue encontrado),
    nombre del producto y si fue encontrado o no.
    Util para detectar productos escaneados repetidamente que no estan en el inventario.
    """
    # Verifica que el modulo de escaneos este disponible (tabla existe en la BD)
    if not ESCANEOS_DISPONIBLE:
        # Devuelve un reporte vacio si el modulo no esta instalado
        df_vacio = pd.DataFrame(
            columns=["Fecha", "Usuario", "Modulo", "Codigo de barras", "Producto", "Encontrado"]
        )
        return ResultadoReporte(
            TITULOS_REPORTE["escaneos"],
            df_vacio,
            resumen={
                "Total de escaneos": 0,
                "Escaneos exitosos": 0,
                "Codigos no encontrados": 0,
            },
        )

    # Trae los registros de escaneo con usuario y producto cargados
    eventos = (
        db.query(EscaneoLog)
        .options(
            joinedload(EscaneoLog.usuario),
            joinedload(EscaneoLog.producto),
        )
        .filter(
            EscaneoLog.fecha >= inicio,
            EscaneoLog.fecha <= fin,
        )
        .order_by(EscaneoLog.fecha.desc())
        .all()
    )

    # Construye una fila por evento de escaneo
    filas = [
        {
            "Fecha": e.fecha.strftime("%Y-%m-%d %H:%M"),
            "Usuario": e.usuario.nombre_completo if e.usuario else "—",
            "Modulo": e.modulo_origen,
            "Codigo de barras": e.codigo_barras or "No registrado",
            "Producto": e.producto.nombre if e.producto else "No encontrado",
            "Encontrado": "Si" if e.encontrado else "No",
        }
        for e in eventos
    ]
    df = pd.DataFrame(
        filas,
        columns=["Fecha", "Usuario", "Modulo", "Codigo de barras", "Producto", "Encontrado"],
    )

    # Calcula las metricas del resumen
    total = len(df)
    exitosos = int((df["Encontrado"] == "Si").sum()) if not df.empty else 0
    no_encontrados = total - exitosos

    resumen = {
        "Total de escaneos": total,
        "Escaneos exitosos": exitosos,
        "Codigos no encontrados": no_encontrados,
    }
    return ResultadoReporte(
        TITULOS_REPORTE["escaneos"],
        df,
        columnas_moneda=[],
        resumen=resumen,
    )