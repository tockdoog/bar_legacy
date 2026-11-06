// frontend/src/utils/formato.js
// Utilidades de formato: pesos colombianos (COP) y fechas en la zona horaria
// America/Bogota.
//
// IMPORTANTE: el backend guarda las fechas como hora local de Colombia SIN zona horaria
// (ej. "2026-11-04T14:30:00"). Si el navegador las interpretara como hora local del
// dispositivo, se mostrarían desfasadas en equipos con otra zona. Por eso se leen como si
// fueran UTC y se muestran con timeZone "UTC" (el reloj queda tal cual lo guardó el
// servidor). Las fechas que sí traen zona explícita ("Z" o "+00:00") se convierten a Bogotá.
//
// CAMBIO: interpretarFecha ahora se exporta (la reutiliza utils/tiempo.js, antes duplicaba
// la lectura) y recorta los decimales de segundo a 3 dígitos: Python envía 6 y algunos
// navegadores (Safari) no los aceptan.

const ZONA_BOGOTA = 'America/Bogota';
const TIENE_ZONA = /(Z|[+-]\d{2}:?\d{2})$/i;

// Marca que indica "fecha sin zona del backend, leída como reloj de pared en UTC"
export const ZONA_FECHA_SIN_ZONA = 'UTC';

// --- Bloque: formateador de moneda COP, sin decimales ---
const formateadorCOP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export function formatearCOP(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return '—';
  return formateadorCOP.format(Number(valor));
}

export function formatearNumero(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return '—';
  return new Intl.NumberFormat('es-CO').format(Number(valor));
}

// --- Bloque: interpreta el texto de fecha del backend sin desfases ---
// Devuelve { fecha, zona } o null si el valor no es una fecha válida.
export function interpretarFecha(valor) {
  if (!valor) return null;
  if (valor instanceof Date) return { fecha: valor, zona: ZONA_BOGOTA };

  let texto = String(valor).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) texto = `${texto}T00:00:00`;
  // Cambia el espacio por "T" y deja máximo 3 decimales de segundo
  texto = texto.replace(' ', 'T').replace(/(\.\d{3})\d+/, '$1');

  const conZona = TIENE_ZONA.test(texto);
  const fecha = new Date(conZona ? texto : `${texto}Z`);
  if (Number.isNaN(fecha.getTime())) return null;
  return { fecha, zona: conZona ? ZONA_BOGOTA : ZONA_FECHA_SIN_ZONA };
}

// --- Bloque: fecha legible en español (ej. "4 nov 2026, 2:30 p. m.") ---
export function formatearFecha(valor, conHora = true) {
  const datos = interpretarFecha(valor);
  if (!datos) return '—';
  const opciones = { timeZone: datos.zona, day: 'numeric', month: 'short', year: 'numeric' };
  if (conHora) {
    opciones.hour = 'numeric';
    opciones.minute = '2-digit';
    opciones.hour12 = true;
  }
  return new Intl.DateTimeFormat('es-CO', opciones).format(datos.fecha);
}

// --- Bloque: hora actual de Bogotá (ej. "2:30 p. m.") ---
export function horaActualBogota() {
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: ZONA_BOGOTA,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date());
}

// --- Bloque: fecha de hoy en Bogotá con formato AAAA-MM-DD (filtros de reportes) ---
export function hoyBogota() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: ZONA_BOGOTA,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}