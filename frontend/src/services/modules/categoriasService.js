// frontend/src/services/modules/categoriasService.js
// Servicios de categorías (rutas de app/routers/categorias.py). Crear, editar y
// eliminar solo lo permite el backend al administrador.

import api from '../api.js';

export async function crearCategoria(datos) {
  const { data } = await api.post('/api/categorias/', datos);
  return data;
}

export async function actualizarCategoria(categoriaId, datos) {
  const { data } = await api.put(`/api/categorias/${categoriaId}`, datos);
  return data;
}

export async function eliminarCategoria(categoriaId) {
  await api.delete(`/api/categorias/${categoriaId}`);
}