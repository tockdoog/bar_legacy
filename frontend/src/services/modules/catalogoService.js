// frontend/src/services/modules/catalogoService.js
// Servicios de lectura del catálogo que usan el POS y Compras: productos,
// categorías y promociones activas, más el registro de escaneos en la bitácora.
// CAMBIO: registrarEscaneo recibe el módulo de origen ("pos" por defecto, o
// "compras"/"inventario"); el backend solo acepta esos tres valores.

import api from '../api.js';

// Bloque: productos activos (las rutas con barra final evitan redirecciones)
export async function listarProductos() {
  const { data } = await api.get('/api/productos/');
  return data;
}

// Bloque: categorías de productos
export async function listarCategorias() {
  const { data } = await api.get('/api/categorias/');
  return data;
}

// Bloque: promociones activas (un empleado recibe costos y ganancia en null)
export async function listarPromociones() {
  const { data } = await api.get('/api/promociones/');
  return data;
}

// Bloque: bitácora de escaneos. Es informativa: si falla, no debe estorbar al usuario.
export async function registrarEscaneo(codigo, encontrado, origen = 'pos') {
  try {
    await api.post('/api/escaner/bitacora', {
      codigo_escaneado: codigo,
      origen,
      encontrado,
    });
  } catch {
    // Sin acciones: la bitácora nunca interrumpe el flujo del usuario
  }
}