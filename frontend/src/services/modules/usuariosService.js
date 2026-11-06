// frontend/src/services/modules/usuariosService.js
// Servicios de gestión de usuarios (app/routers/usuarios.py). Todo, salvo el
// cambio de la propia contraseña (authService.js), es exclusivo del administrador.

import api from '../api.js';

export async function listarUsuarios() {
  const { data } = await api.get('/api/usuarios/');
  return data; // [{ id, nombre_completo, nombre_usuario, correo, rol, activo, permisos }]
}

// Bloque: catálogo de permisos granulares [{ clave, descripcion }]
export async function listarPermisosDisponibles() {
  const { data } = await api.get('/api/usuarios/permisos-disponibles');
  return data;
}

export async function crearUsuario(datos) {
  const { data } = await api.post('/api/usuarios/', datos);
  return data;
}

// Bloque: edición parcial; sirve también para activar o desactivar ({ activo })
export async function actualizarUsuario(usuarioId, datos) {
  const { data } = await api.put(`/api/usuarios/${usuarioId}`, datos);
  return data;
}

// Bloque: el administrador asigna una contraseña nueva (responde 204 sin contenido)
export async function restablecerContrasena(usuarioId, contrasenaNueva) {
  await api.post(`/api/usuarios/${usuarioId}/restablecer-contrasena`, {
    contrasena_nueva: contrasenaNueva,
  });
}