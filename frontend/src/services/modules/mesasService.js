// frontend/src/services/modules/mesasService.js
// Servicios de mesas: listar (con su venta abierta), crear, eliminar y bloqueo
// colaborativo. Crear y eliminar solo los permite el backend al administrador.

import api, { leerSesion, urlApi } from '../api.js';

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

// Bloque: bloqueos vigentes [{ mesa_id, nombre_completo, nombre_usuario, desde, es_mio }]
export async function listarBloqueos() {
  const { data } = await api.get('/api/mesas/bloqueos');
  return data;
}

// Bloque: toma o renueva (latido) el bloqueo; responde 409 si otro usuario atiende la mesa
export async function tomarBloqueo(mesaId) {
  const { data } = await api.post(`/api/mesas/${mesaId}/bloqueo`);
  return data;
}

// Bloque: libera el bloqueo al salir. Usa fetch con "keepalive" para que la petición
// termine aunque la pestaña se esté cerrando (Axios no lo permite). Si no llega, el
// bloqueo expira solo por falta de latido.
export function liberarBloqueoAlSalir(mesaId) {
  const token = leerSesion()?.token;
  if (!token) return;
  fetch(`${urlApi}/api/mesas/${mesaId}/bloqueo`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
    keepalive: true,
  }).catch(() => {});
}