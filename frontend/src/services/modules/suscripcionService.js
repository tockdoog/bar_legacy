// frontend/src/services/modules/suscripcionService.js
// Servicio de suscripción: estado del pago mensual, cuentas de pago del
// proveedor y desbloqueo con la clave maestra. Estas rutas del backend están
// excluidas del bloqueo, por lo que responden aunque el sistema esté bloqueado.
// Nota: "fecha_vencimiento" llega en UTC sin zona (ver PanelSuscripcion).

import api from '../api.js';

// Bloque: días restantes, si está bloqueado, vencimiento y valor mensual en COP
export async function obtenerEstadoSuscripcion() {
  const { data } = await api.get('/api/suscripcion/estado');
  return data;
}

// Bloque: cuentas/medios de pago del proveedor [{ nombre, tipo_dato, valor, imagen_url }]
export async function listarCuentasPago() {
  const { data } = await api.get('/api/suscripcion/cuentas-pago');
  return data;
}

// Bloque: desbloquea con la clave maestra (solo administrador). Devuelve el estado nuevo.
export async function desbloquearSistema(clave) {
  const { data } = await api.post('/api/suscripcion/desbloquear', { clave });
  return data;
}