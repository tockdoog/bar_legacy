// frontend/src/utils/tiempo.js
// Tiempo transcurrido desde una fecha del backend. El backend guarda hora local de
// Colombia SIN zona, así que "ahora" también se calcula en hora de Bogotá (UTC-5 fijo,
// Colombia no tiene horario de verano). La lectura de la fecha se comparte con
// utils/formato.js para que ambos archivos interpreten las fechas igual.

import { ZONA_FECHA_SIN_ZONA, interpretarFecha } from './formato.js';

const DESFASE_BOGOTA_MS = 5 * 60 * 60 * 1000;

// Bloque: minutos transcurridos desde una fecha (nulo si la fecha no es válida)
export function minutosDesde(fecha) {
  const datos = interpretarFecha(fecha);
  if (!datos) return null;

  // Fecha sin zona: se compara contra el reloj de Bogotá; con zona, contra el instante real
  const ahora = datos.zona === ZONA_FECHA_SIN_ZONA ? Date.now() - DESFASE_BOGOTA_MS : Date.now();
  return Math.max(Math.floor((ahora - datos.fecha.getTime()) / 60000), 0);
}

// Bloque: texto legible de una duración en minutos
export function textoDuracion(minutos) {
  if (minutos === null || minutos === undefined) return '—';
  if (minutos < 1) return 'Hace un momento';
  if (minutos < 60) return `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}