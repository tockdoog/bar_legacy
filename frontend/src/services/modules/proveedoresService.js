// frontend/src/services/modules/proveedoresService.js
// Servicios de proveedores (app/routers/proveedores.py). Todo el módulo exige
// el permiso "compras_gestionar".

import api from '../api.js';

export async function listarProveedores() {
  const { data } = await api.get('/api/proveedores/');
  return data; // [{ id, nombre, telefono, canal, notas }]
}

export async function crearProveedor(datos) {
  const { data } = await api.post('/api/proveedores/', datos);
  return data;
}

export async function actualizarProveedor(proveedorId, datos) {
  const { data } = await api.put(`/api/proveedores/${proveedorId}`, datos);
  return data;
}

// Bloque: el backend rechaza eliminar un proveedor que ya tiene compras registradas
export async function eliminarProveedor(proveedorId) {
  await api.delete(`/api/proveedores/${proveedorId}`);
}