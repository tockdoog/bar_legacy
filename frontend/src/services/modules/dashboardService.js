// frontend/src/services/modules/dashboardService.js
// Servicios que alimentan el Dashboard. Usan únicamente endpoints existentes
// del backend. Los reportes requieren el permiso "reportes_ver".

import api from '../api.js';

// Bloque: reporte por tipo ("ganancias", "ventas", "mas-vendidos") y rango AAAA-MM-DD
export async function obtenerReporte(tipo, fechaInicio, fechaFin) {
  const { data } = await api.get(`/api/reportes/${tipo}`, {
    params: { fecha_inicio: fechaInicio, fecha_fin: fechaFin },
  });
  return data; // { titulo, columnas, columnas_moneda, filas, resumen }
}

// Bloque: productos cuyo stock llegó o bajó del mínimo
export async function obtenerInventarioBajo() {
  const { data } = await api.get('/api/productos/inventario-bajo');
  return data;
}

// Bloque: mesas con su estado (libre, ocupada, pendiente_pago)
export async function obtenerMesas() {
  const { data } = await api.get('/api/mesas/');
  return data;
}

// Bloque: ventas abiertas (cuentas en curso)
export async function obtenerVentasAbiertas() {
  const { data } = await api.get('/api/ventas/abiertas');
  return data;
}