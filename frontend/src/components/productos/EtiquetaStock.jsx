// frontend/src/components/productos/EtiquetaStock.jsx
// Insignia de color con el estado de existencias de un producto.

import { ETIQUETAS_STOCK, estadoStock } from '../../utils/inventario.js';

export default function EtiquetaStock({ producto }) {
  const { texto, tono } = ETIQUETAS_STOCK[estadoStock(producto)];
  return <span className={`etiqueta ${tono}`}>{texto}</span>;
}