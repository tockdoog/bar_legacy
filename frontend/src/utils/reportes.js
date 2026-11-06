// frontend/src/utils/reportes.js
// Catálogo de los reportes del backend (lista blanca TIPOS_VALIDOS de
// generador_reportes.py), periodos rápidos y cálculos para las gráficas.
// Sin acceso a la API.

import { restarDias } from './indicadores.js';

// Bloque: tipos de reporte; "usaFechas" indica si el backend filtra por rango
export const TIPOS_REPORTE = [
  { id: 'ventas', etiqueta: 'Ventas', descripcion: 'Ventas cobradas en el periodo.', usaFechas: true },
  { id: 'ventas-anuladas', etiqueta: 'Anuladas', descripcion: 'Ventas anuladas: productos, quién las anuló y motivo.', usaFechas: true },
  { id: 'compras', etiqueta: 'Compras', descripcion: 'Compras a proveedores, con detalle por producto.', usaFechas: true },
  { id: 'inventario', etiqueta: 'Inventario', descripcion: 'Existencias actuales y su valor (no depende de fechas).', usaFechas: false },
  { id: 'mas-vendidos', etiqueta: 'Más vendidos', descripcion: 'Los 15 productos con más unidades vendidas.', usaFechas: true },
  { id: 'menos-vendidos', etiqueta: 'Menos vendidos', descripcion: 'Los 15 productos con menos unidades vendidas.', usaFechas: true },
  { id: 'ganancias', etiqueta: 'Ganancias', descripcion: 'Ventas, costo y ganancia estimada por día.', usaFechas: true },
  { id: 'escaneos', etiqueta: 'Escaneos', descripcion: 'Actividad del lector de códigos de barras.', usaFechas: true },
];

// Bloque: periodos rápidos; todos terminan hoy (fecha de Bogotá, AAAA-MM-DD)
export const PERIODOS = [
  { id: 'hoy', etiqueta: 'Hoy' },
  { id: '7d', etiqueta: '7 días' },
  { id: '30d', etiqueta: '30 días' },
  { id: 'mes', etiqueta: 'Este mes' },
];

export function rangoPeriodo(id, hoy) {
  if (id === 'hoy') return { desde: hoy, hasta: hoy };
  if (id === '7d') return { desde: restarDias(hoy, 6), hasta: hoy };
  if (id === 'mes') return { desde: `${hoy.slice(0, 8)}01`, hasta: hoy };
  return { desde: restarDias(hoy, 29), hasta: hoy };
}

// Bloque: indica si un dato del resumen es dinero (misma regla que formato_reportes.py)
export const esResumenMonetario = (etiqueta) =>
  /monto|ganancia|costo|valor|ventas totales|total (en|vendido|anulado)/i.test(etiqueta);

// Bloque: suma un campo por día (la fecha viene como "AAAA-MM-DD" o "AAAA-MM-DD HH:MM")
export function serieSumaPorDia(filas, campo) {
  const porDia = new Map();
  filas.forEach((fila) => {
    const dia = String(fila.Fecha).slice(0, 10);
    porDia.set(dia, (porDia.get(dia) || 0) + Number(fila[campo] || 0));
  });
  return [...porDia.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dia, valor]) => ({ etiqueta: `${dia.slice(8, 10)}/${dia.slice(5, 7)}`, valor }));
}