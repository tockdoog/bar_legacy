// frontend/src/utils/tiempo.js
// Tiempo transcurrido desde una fecha del backend. El backend guarda hora local
// de Colombia SIN zona, así que "ahora" también se calcula en hora de Bogotá
// (UTC-5 fijo, Colombia no tiene horario de verano).

const DESFASE_BOGOTA_MS = 5 * 60 * 60 * 1000;

// Bloque: minutos transcurridos desde una fecha (nulo si la fecha no es válida)
export function minutosDesde(fecha) {
  if (!fecha) return null;
  const texto = String(fecha).trim().replace(' ', 'T');
  const conZona = /(Z|[+-]\d{2}:?\d{2})$/i.test(texto);
  const ms = new Date(conZona ? texto : `${texto}Z`).getTime();
  if (Number.isNaN(ms)) return null;
  const ahora = conZona ? Date.now() : Date.now() - DESFASE_BOGOTA_MS;
  return Math.max(Math.floor((ahora - ms) / 60000), 0);
}

// Bloque: texto legible de una duración en minutos
export function textoDuracion(minutos) {
  if (minutos === null || minutos === undefined) return '—';
  if (minutos < 1) return 'Hace un momento';
  if (minutos < 60) return `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}