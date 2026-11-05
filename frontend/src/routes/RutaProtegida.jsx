// frontend/src/routes/RutaProtegida.jsx
// Protege rutas: exige sesión y, opcionalmente, un rol o un permiso granular.
// Uso: <Route element={<RutaProtegida roles={['administrador']} />}> ... </Route>
// o   <Route element={<RutaProtegida permiso="inventario_gestionar" />}> ...
// El backend vuelve a validar cada petición; esto solo mejora la experiencia.

import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';

export default function RutaProtegida({ roles, permiso, children }) {
  const { autenticado, cargando, usuario, tienePermiso } = useAuth();
  const ubicacion = useLocation();

  // Bloque: mientras se valida la sesión guardada, muestra un indicador de carga
  if (cargando) {
    return (
      <div className="pantalla-centrada" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p className="texto-suave">Verificando sesión…</p>
      </div>
    );
  }

  // Bloque: sin sesión, redirige al login recordando a dónde quería ir
  if (!autenticado) {
    return <Navigate to="/login" replace state={{ desde: ubicacion }} />;
  }

  // Bloque: valida rol o permiso; si no cumple, muestra aviso de acceso denegado
  const rolPermitido = !roles || roles.includes(usuario.rol);
  const permisoPermitido = !permiso || tienePermiso(permiso);
  if (!rolPermitido || !permisoPermitido) {
    return (
      <div className="pantalla-centrada">
        <ShieldAlert size={40} color="var(--rojo)" aria-hidden="true" />
        <h2>Acceso restringido</h2>
        <p className="texto-suave">No tienes permisos para ver esta sección.</p>
      </div>
    );
  }

  return children || <Outlet />;
}