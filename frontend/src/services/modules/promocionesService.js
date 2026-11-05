// frontend/src/services/modules/promocionesService.js
// Servicios de gestión de promociones (app/routers/promociones.py). Crear,
// editar y activar/desactivar solo lo permite el backend al administrador.

import api from '../api.js';

// Bloque: lista promociones; con "incluirInactivas" el administrador ve también las desactivadas
export async function listarPromocionesGestion(incluirInactivas = false) {
  const { data } = await api.get('/api/promociones/', {
    params: incluirInactivas ? { incluir_inactivas: true } : undefined,
  });
  return data;
}

// Bloque: "items" es [{ producto_id, cantidad }]
export async function crearPromocion(datos) {
  const { data } = await api.post('/api/promociones/', datos);
  return data;
}

// Bloque: edición parcial; sirve también para activar o desactivar ({ activa: true|false })
export async function actualizarPromocion(promocionId, datos) {
  const { data } = await api.put(`/api/promociones/${promocionId}`, datos);
  return data;
}