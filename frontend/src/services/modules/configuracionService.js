// frontend/src/services/modules/configuracionService.js
// Servicios de configuración: impuestos y margen del negocio (requiere el
// permiso "finanzas_gestionar") y código QR para vincular dispositivos
// (solo administrador). Los tipos de impuesto se piden con
// productosService.listarTiposImpuesto().

import api from '../api.js';

export async function obtenerConfiguracionFinanciera() {
  const { data } = await api.get('/api/finanzas/configuracion');
  return data;
}

export async function actualizarConfiguracionFinanciera(datos) {
  const { data } = await api.put('/api/finanzas/configuracion', datos);
  return data;
}

// Bloque: QR con la URL de acceso en la red local { url_acceso, imagen_qr_base64 }
export async function obtenerQrDispositivo() {
  const { data } = await api.get('/api/qr/dispositivo');
  return data;
}