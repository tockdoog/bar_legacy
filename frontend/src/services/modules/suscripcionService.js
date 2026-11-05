// frontend/src/services/modules/suscripcionService.js
// Servicio de suscripción: estado del pago mensual. Esta ruta del backend está
// excluida del bloqueo, por lo que responde aunque el sistema esté bloqueado.

import api from '../api.js';

// Bloque: días restantes, si está bloqueado, vencimiento y valor mensual en COP
export async function obtenerEstadoSuscripcion() {
  const { data } = await api.get('/api/suscripcion/estado');
  return data;
}