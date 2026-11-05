// frontend/src/services/modules/comprasService.js
// Servicios de compras a proveedores (app/routers/compras.py). Registrar una
// compra aumenta las existencias y actualiza el costo de cada producto.

import api from '../api.js';

// Bloque: historial de compras con sus detalles, de la más reciente a la más antigua
export async function listarCompras() {
  const { data } = await api.get('/api/compras/');
  return data;
}

// Bloque: registra una compra. "items" es [{ producto_id, cantidad, costo_unitario }]
export async function registrarCompra(proveedorId, items) {
  const { data } = await api.post('/api/compras/', { proveedor_id: proveedorId, items });
  return data;
}