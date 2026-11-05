// frontend/src/utils/pos.js
// Utilidades del cobro: métodos de pago, conversión de texto a pesos enteros y
// evaluación de pagos (recibido, cambio y faltante). Sin acceso a la API.

// Bloque: métodos de pago aceptados por el backend (MetodoPago). "mixto" lo asigna
// el servidor solo cuando se usan varios métodos, por eso no aparece aquí.
export const METODOS_PAGO = [
  { valor: 'efectivo', etiqueta: 'Efectivo' },
  { valor: 'nequi', etiqueta: 'Nequi' },
  { valor: 'daviplata', etiqueta: 'Daviplata' },
  { valor: 'bancolombia', etiqueta: 'Bancolombia' },
  { valor: 'tarjeta_debito', etiqueta: 'Tarjeta débito' },
  { valor: 'tarjeta_credito', etiqueta: 'Tarjeta crédito' },
  { valor: 'otro', etiqueta: 'Otro' },
];

export const etiquetaMetodo = (valor) =>
  METODOS_PAGO.find((metodo) => metodo.valor === valor)?.etiqueta || valor;

// Bloque: convierte un texto como "$ 48.000" en el entero 48000
export function aEntero(texto) {
  const digitos = String(texto ?? '').replace(/\D/g, '');
  return digitos ? parseInt(digitos, 10) : 0;
}

// Bloque: formatea un entero con separador de miles ("48.000"); vacío si es 0
export function formatearMiles(numero) {
  return numero ? new Intl.NumberFormat('es-CO').format(numero) : '';
}

// Bloque: evalúa los pagos frente al total.
// - El backend exige pagar al menos el total (por eso se redondea hacia arriba).
// - El cambio solo puede devolverse de lo recibido en efectivo.
export function evaluarPagos(pagos, total) {
  const totalEntero = Math.ceil(total - 0.0001);
  const recibido = pagos.reduce((suma, pago) => suma + pago.monto, 0);
  const efectivo = pagos
    .filter((pago) => pago.metodo_pago === 'efectivo')
    .reduce((suma, pago) => suma + pago.monto, 0);

  const cambio = Math.max(recibido - totalEntero, 0);
  const faltante = Math.max(totalEntero - recibido, 0);
  const cambioImposible = cambio > efectivo;

  return {
    totalEntero,
    recibido,
    cambio,
    faltante,
    cambioImposible,
    valido: totalEntero > 0 && pagos.length > 0 && faltante === 0 && !cambioImposible,
  };
}