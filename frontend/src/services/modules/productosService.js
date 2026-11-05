// frontend/src/services/modules/productosService.js
// Servicios de gestión de productos (rutas de app/routers/productos.py). Crear,
// editar, eliminar y manejar imágenes requiere el permiso "inventario_gestionar".

import api from '../api.js';

export async function crearProducto(datos) {
  const { data } = await api.post('/api/productos/', datos);
  return data;
}

export async function actualizarProducto(productoId, datos) {
  const { data } = await api.put(`/api/productos/${productoId}`, datos);
  return data;
}

// Bloque: eliminación lógica (el backend desactiva el producto y conserva su historial)
export async function eliminarProducto(productoId) {
  await api.delete(`/api/productos/${productoId}`);
}

// Bloque: sube la imagen como multipart; el campo se llama "archivo" en el backend
export async function subirImagenProducto(productoId, archivo) {
  const formulario = new FormData();
  formulario.append('archivo', archivo);
  const { data } = await api.post(`/api/productos/${productoId}/imagen`, formulario);
  return data;
}

export async function quitarImagenProducto(productoId) {
  const { data } = await api.delete(`/api/productos/${productoId}/imagen`);
  return data;
}

// Bloque: tipos de impuesto con su porcentaje de referencia (requiere "finanzas_gestionar")
export async function listarTiposImpuesto() {
  const { data } = await api.get('/api/finanzas/impuestos-disponibles');
  return data; // [{ tipo, etiqueta, porcentaje_referencia }]
}