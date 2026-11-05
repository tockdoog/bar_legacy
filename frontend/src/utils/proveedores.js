// frontend/src/utils/proveedores.js
// Canales de pedido de un proveedor, iguales al enum CanalProveedor del backend.

export const CANALES = [
  { valor: 'rappi', etiqueta: 'Rappi' },
  { valor: 'didi', etiqueta: 'DiDi' },
  { valor: 'llamada', etiqueta: 'Llamada telefónica' },
  { valor: 'distribuidor', etiqueta: 'Distribuidor' },
  { valor: 'otro', etiqueta: 'Otro' },
];

// Bloque: texto legible de un canal (si llega uno desconocido, se muestra tal cual)
export const etiquetaCanal = (valor) => CANALES.find((c) => c.valor === valor)?.etiqueta || valor;