// frontend/src/services/modules/mesasService.js
// Servicios de mesas: listar (con su venta abierta), crear y eliminar.
// Crear y eliminar solo los permite el backend al administrador.

import api from '../api.js';

export async function listarMesas() {
  const { data } = await api.get('/api/mesas/');
  return data; // [{ id, numero, estado, venta_abierta_id }]
}

export async function crearMesa(numero) {
  const { data } = await api.post('/api/mesas/', { numero });
  return data;
}

export async function eliminarMesa(mesaId) {
  await api.delete(`/api/mesas/${mesaId}`);
}