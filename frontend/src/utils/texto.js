// frontend/src/utils/texto.js
// Utilidades de texto compartidas por las pantallas con búsqueda.

// Bloque: texto sin tildes ni mayúsculas, para que la búsqueda no distinga entre ellas
export const normalizar = (texto) =>
  String(texto || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();