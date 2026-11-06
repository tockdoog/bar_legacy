// frontend/src/services/api.js
// Cliente HTTP central (Axios): URL del backend desde variables de entorno,
// token Bearer automático, manejo uniforme de errores (401, 423, 429, red) y
// almacenamiento de sesión.
//
// SEGURIDAD: el token se guarda en sessionStorage (se borra al cerrar la
// pestaña). El backend usa tokens Bearer, no cookies HttpOnly, por eso la CSP
// de vercel.json bloquea scripts externos para reducir el riesgo de XSS.
//
// CORRECCIÓN: el desbloqueo con clave incorrecta responde 401; ya no se trata
// como "sesión vencida" (antes cerraba la sesión del administrador).

import axios from 'axios';

// --- Bloque: configuración base ---
const URL_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
const CLAVE_SESION = 'barlegacy.sesion';

export const urlApi = URL_BASE;
export const EVENTO_SESION_EXPIRADA = 'barlegacy:sesion-expirada';
export const EVENTO_SISTEMA_BLOQUEADO = 'barlegacy:sistema-bloqueado';

// Rutas donde un 401 significa "datos incorrectos" y no "sesión vencida"
const RUTAS_401_PROPIO = ['/api/auth/login', '/api/suscripcion/desbloquear'];

// --- Bloque: manejo de la sesión guardada en el navegador ---
export function guardarSesion(sesion) {
  try {
    sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
  } catch {
    // Si el almacenamiento no está disponible, la sesión vive solo en memoria
  }
}

export function leerSesion() {
  try {
    const texto = sessionStorage.getItem(CLAVE_SESION);
    return texto ? JSON.parse(texto) : null;
  } catch {
    return null;
  }
}

export function limpiarSesion() {
  try {
    sessionStorage.removeItem(CLAVE_SESION);
  } catch {
    // Sin acciones: no hay nada que limpiar si el almacenamiento falla
  }
}

// --- Bloque: construye la URL completa de imágenes servidas por el backend ---
// Solo acepta rutas relativas que empiecen por "/" (evita URLs externas inesperadas).
export function urlImagen(ruta) {
  if (!ruta) return null;
  if (/^https?:\/\//i.test(ruta)) return ruta;
  if (!ruta.startsWith('/') || ruta.startsWith('//')) return null;
  return `${URL_BASE}${ruta}`;
}

// --- Bloque: instancia de Axios ---
const api = axios.create({
  baseURL: URL_BASE,
  timeout: 20000,
});

// Antes de cada petición: adjunta el token JWT si existe una sesión
api.interceptors.request.use((config) => {
  const sesion = leerSesion();
  if (sesion?.token) {
    config.headers.Authorization = `Bearer ${sesion.token}`;
  }
  return config;
});

// Después de cada respuesta: reacciona a sesión vencida (401) y sistema bloqueado (423)
api.interceptors.response.use(
  (respuesta) => respuesta,
  (error) => {
    const estado = error.response?.status;
    const url = String(error.config?.url || '');
    const es401Propio = RUTAS_401_PROPIO.some((ruta) => url.includes(ruta));
    const esLogin = url.includes('/api/auth/login');

    if (estado === 401 && !es401Propio) {
      limpiarSesion();
      window.dispatchEvent(new CustomEvent(EVENTO_SESION_EXPIRADA));
    }
    // En el login, un 423 significa "cuenta bloqueada"; en el resto, "suscripción vencida"
    if (estado === 423 && !esLogin) {
      window.dispatchEvent(
        new CustomEvent(EVENTO_SISTEMA_BLOQUEADO, { detail: error.response?.data?.detail })
      );
    }
    return Promise.reject(error);
  }
);

// --- Bloque: convierte cualquier error de Axios en un mensaje claro en español ---
export function mensajeDeError(error) {
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED') {
      return 'El servidor tardó demasiado en responder. Intenta de nuevo.';
    }
    return 'No fue posible conectar con el servidor. Revisa tu conexión a internet.';
  }

  const { status, data } = error.response;

  // slowapi responde en inglés, se traduce aquí
  if (status === 429) return 'Demasiadas solicitudes seguidas. Espera un momento e intenta de nuevo.';
  if (status >= 500) return 'Ocurrió un error interno en el servidor. Intenta más tarde.';

  const detalle = data?.detail;
  if (typeof detalle === 'string') return detalle;

  // Errores de validación de FastAPI (422): lista de {loc, msg}
  if (Array.isArray(detalle)) {
    return detalle
      .map((item) => {
        const campo = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
        return campo ? `${campo}: ${item.msg}` : item.msg;
      })
      .join(' · ');
  }
  return 'No se pudo completar la operación.';
}

export default api;