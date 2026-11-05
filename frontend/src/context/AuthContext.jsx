// frontend/src/context/AuthContext.jsx
// Contexto de autenticación: guarda la sesión, la revalida contra /api/auth/yo
// al cargar (el rol y los permisos siempre vienen de la base de datos), cierra
// la sesión automáticamente cuando el JWT expira y expone helpers de permisos.
//
// SEGURIDAD: ocultar botones según rol/permiso es solo comodidad visual; el
// backend sigue siendo quien valida cada petición.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
  EVENTO_SESION_EXPIRADA,
  guardarSesion,
  leerSesion,
  limpiarSesion,
} from '../services/api.js';
import { iniciarSesionServicio, obtenerPerfilServicio } from '../services/modules/authService.js';

const ContextoAuth = createContext(null);
const MAXIMO_TIMEOUT_MS = 2147483647; // Límite de setTimeout (~24,8 días)

// --- Bloque: lee la fecha de expiración (exp) del JWT sin verificar la firma ---
// Solo sirve para programar el cierre de sesión; la validez real la decide el backend.
function leerExpiracionMs(token) {
  try {
    const carga = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const datos = JSON.parse(atob(carga));
    return datos.exp ? datos.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(() => leerSesion());
  const [cargando, setCargando] = useState(true);

  // Bloque: cierra la sesión local (el backend no mantiene sesiones en servidor)
  const cerrarSesion = useCallback((mensaje) => {
    limpiarSesion();
    setSesion(null);
    if (mensaje) toast.info(mensaje, { id: 'sesion-cerrada' });
  }, []);

  // Bloque: al cargar la app, revalida el token y refresca rol y permisos desde la BD
  useEffect(() => {
    const guardada = leerSesion();
    if (!guardada?.token) {
      setCargando(false);
      return;
    }
    obtenerPerfilServicio()
      .then((perfil) => {
        const actualizada = {
          ...guardada,
          rol: perfil.rol,
          nombre_completo: perfil.nombre_completo,
          permisos: perfil.permisos || [],
        };
        guardarSesion(actualizada);
        setSesion(actualizada);
      })
      .catch((error) => {
        // Solo se descarta la sesión si el token es inválido; un fallo de red no cierra sesión
        if (error.response?.status === 401) {
          limpiarSesion();
          setSesion(null);
        }
      })
      .finally(() => setCargando(false));
  }, []);

  // Bloque: escucha el evento que emite api.js cuando el backend responde 401
  useEffect(() => {
    const alExpirar = () => {
      setSesion(null);
      toast.warning('Tu sesión expiró. Inicia sesión nuevamente.', { id: 'sesion-expirada' });
    };
    window.addEventListener(EVENTO_SESION_EXPIRADA, alExpirar);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, alExpirar);
  }, []);

  // Bloque: programa el cierre automático de sesión cuando el token expira
  useEffect(() => {
    if (!sesion?.token) return undefined;
    const expiracion = leerExpiracionMs(sesion.token);
    if (!expiracion) return undefined;

    const restante = expiracion - Date.now();
    if (restante <= 0) {
      cerrarSesion('Tu sesión expiró. Inicia sesión nuevamente.');
      return undefined;
    }
    const temporizador = setTimeout(
      () => cerrarSesion('Tu sesión expiró. Inicia sesión nuevamente.'),
      Math.min(restante, MAXIMO_TIMEOUT_MS)
    );
    return () => clearTimeout(temporizador);
  }, [sesion?.token, cerrarSesion]);

  // Bloque: inicio de sesión; los errores los maneja la pantalla de login
  const iniciarSesion = useCallback(async (usuario, contrasena) => {
    const datos = await iniciarSesionServicio(usuario, contrasena);
    const nueva = {
      token: datos.token_acceso,
      rol: datos.rol,
      nombre_completo: datos.nombre_completo,
      permisos: datos.permisos || [],
    };
    guardarSesion(nueva);
    setSesion(nueva);
  }, []);

  // Bloque: valor expuesto; el administrador tiene todos los permisos por su rol
  const valor = useMemo(() => {
    const esAdmin = sesion?.rol === 'administrador';
    return {
      usuario: sesion
        ? { rol: sesion.rol, nombre_completo: sesion.nombre_completo, permisos: sesion.permisos }
        : null,
      autenticado: Boolean(sesion?.token),
      cargando,
      esAdmin,
      tienePermiso: (clave) => esAdmin || (sesion?.permisos || []).includes(clave),
      iniciarSesion,
      cerrarSesion: () => cerrarSesion('Sesión cerrada correctamente.'),
    };
  }, [sesion, cargando, iniciarSesion, cerrarSesion]);

  return <ContextoAuth.Provider value={valor}>{children}</ContextoAuth.Provider>;
}

// Hook de acceso al contexto de autenticación
export function useAuth() {
  const contexto = useContext(ContextoAuth);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}