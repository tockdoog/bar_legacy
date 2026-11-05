// frontend/src/utils/indicadores.js
// Cálculos puros para el Dashboard: operaciones con fechas AAAA-MM-DD (en hora
// de Bogotá, tal como las entrega el backend), sumas por periodo, series
// diarias y variación porcentual. Sin dependencias ni acceso a la API.

// Bloque: resta días a una fecha AAAA-MM-DD sin depender de la zona del dispositivo
export function restarDias(fechaIso, dias) {
  const [anio, mes, dia] = fechaIso.split('-').map(Number);
  return new Date(Date.UTC(anio, mes - 1, dia - dias)).toISOString().slice(0, 10);
}

// Bloque: toma solo la parte de fecha de un texto ("2026-11-04 14:30" -> "2026-11-04")
function soloDia(valor) {
  return String(valor).slice(0, 10);
}

// Bloque: suma un campo numérico de las filas cuya fecha está entre "desde" y "hasta" (inclusive)
export function sumarCampo(filas, campo, desde, hasta) {
  return filas.reduce((total, fila) => {
    const dia = soloDia(fila.Fecha);
    return dia >= desde && dia <= hasta ? total + Number(fila[campo] || 0) : total;
  }, 0);
}

// Bloque: cuenta las filas cuya fecha está entre "desde" y "hasta" (inclusive)
export function contarFilas(filas, desde, hasta) {
  return filas.filter((fila) => {
    const dia = soloDia(fila.Fecha);
    return dia >= desde && dia <= hasta;
  }).length;
}

// Bloque: variación porcentual entre dos valores (nulo si no hay base de comparación)
export function variacionPorcentual(actual, anterior) {
  if (!anterior) return null;
  return ((actual - anterior) / anterior) * 100;
}

// Bloque: serie diaria de los últimos N días, rellenando con 0 los días sin ventas
export function serieDiaria(filas, campo, hoy, dias) {
  const porDia = new Map();
  filas.forEach((fila) => {
    const dia = soloDia(fila.Fecha);
    porDia.set(dia, (porDia.get(dia) || 0) + Number(fila[campo] || 0));
  });

  return Array.from({ length: dias }, (_, indice) => {
    const fecha = restarDias(hoy, dias - 1 - indice);
    return {
      fecha,
      etiqueta: `${fecha.slice(8, 10)}/${fecha.slice(5, 7)}`,
      valor: porDia.get(fecha) || 0,
    };
  });
}