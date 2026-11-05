// frontend/src/services/modules/authService.js
// Servicios de autenticación: login, perfil del usuario en sesión y cambio
// de contraseña propia. Rutas exactas del backend (app/routers/auth.py y usuarios.py).

import api from '../api.js';

// Bloque: inicio de sesión. El backend usa OAuth2PasswordRequestForm, por eso
// se envía como formulario (application/x-www-form-urlencoded), no como JSON.
export async function iniciarSesionServicio(usuario, contrasena) {
  const formulario = new URLSearchParams();
  formulario.append('username', usuario);
  formulario.append('password', contrasena);
  const { data } = await api.post('/api/auth/login', formulario);
  return data; // { token_acceso, tipo_token, rol, nombre_completo, permisos }
}

// Bloque: perfil del usuario autenticado (rol y permisos siempre desde la BD)
export async function obtenerPerfilServicio() {
  const { data } = await api.get('/api/auth/yo');
  return data;
}

// Bloque: cambio de la contraseña propia (responde 204 sin contenido)
export async function cambiarMiContrasenaServicio(contrasenaActual, contrasenaNueva) {
  await api.put('/api/usuarios/me/contrasena', {
    contrasena_actual: contrasenaActual,
    contrasena_nueva: contrasenaNueva,
  });
}