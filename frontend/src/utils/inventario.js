// frontend/src/utils/inventario.js
// Reglas de existencias compartidas por Productos e Inventario: estado de stock,
// su etiqueta visual y el orden de prioridad (lo más urgente primero).

// Bloque: estado según las existencias y el stock mínimo del producto
export function estadoStock(producto) {
  if (producto.stock_actual <= 0) return 'agotado';
  if (producto.stock_actual <= producto.stock_minimo) return 'bajo';
  return 'ok';
}

// Bloque: texto y color de cada estado (los colores existen en layout.css)
export const ETIQUETAS_STOCK = {
  agotado: { texto: 'Agotado', tono: 'rojo' },
  bajo: { texto: 'Stock bajo', tono: 'ambar' },
  ok: { texto: 'Disponible', tono: 'verde' },
};

// Bloque: orden de urgencia (agotados primero, luego stock bajo)
export const PRIORIDAD_STOCK = { agotado: 0, bajo: 1, ok: 2 };