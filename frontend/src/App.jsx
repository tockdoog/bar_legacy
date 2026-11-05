// frontend/src/App.jsx
// Define las rutas de la aplicación: login y diagnóstico (públicos), y el resto
// dentro del layout con sidebar, protegido por sesión, rol y permisos.
// Los módulos ya construidos usan su página real (PAGINAS); los demás muestran
// la pantalla "en construcción" hasta su fase.

import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Toaster, toast } from 'sonner';

import RutaProtegida from './routes/RutaProtegida.jsx';
import { MODULOS } from './routes/navegacion.js';
import LayoutApp from './components/layout/LayoutApp.jsx';
import PaginaPendiente from './components/common/PaginaPendiente.jsx';
import Login from './pages/auth/Login.jsx';
import Inicio from './pages/dashboard/Inicio.jsx';
import PuntoVenta from './pages/pos/PuntoVenta.jsx';
import Mesas from './pages/mesas/Mesas.jsx';
import Diagnostico from './pages/test/Diagnostico.jsx';
import { EVENTO_SISTEMA_BLOQUEADO } from './services/api.js';
import { useAuth } from './context/AuthContext.jsx';

// Bloque: páginas ya construidas, por ruta. Se amplía en cada fase.
const PAGINAS = {
  '/pos': PuntoVenta,
  '/mesas': Mesas,
};

// Bloque: ruta pública que redirige al inicio si ya hay sesión activa
function RutaPublica({ children }) {
  const { autenticado, cargando } = useAuth();
  if (cargando) return null;
  return autenticado ? <Navigate to="/" replace /> : children;
}

export default function App() {
  // Bloque: aviso global cuando el backend responde 423 (suscripción vencida)
  useEffect(() => {
    const alBloquearse = (evento) => {
      toast.error(evento.detail || 'El sistema está bloqueado por falta de pago.', {
        id: 'sistema-bloqueado',
        duration: 8000,
      });
    };
    window.addEventListener(EVENTO_SISTEMA_BLOQUEADO, alBloquearse);
    return () => window.removeEventListener(EVENTO_SISTEMA_BLOQUEADO, alBloquearse);
  }, []);

  return (
    <>
      <Toaster position="top-right" richColors closeButton />
      <Routes>
        {/* Rutas públicas */}
        <Route path="/login" element={<RutaPublica><Login /></RutaPublica>} />
        <Route path="/test" element={<Diagnostico />} />

        {/* Rutas privadas dentro del layout con sidebar */}
        <Route element={<RutaProtegida />}>
          <Route element={<LayoutApp />}>
            <Route index element={<Inicio />} />

            {/* Un módulo por entrada de navegación, con su rol o permiso requerido */}
            {MODULOS.filter((modulo) => modulo.ruta !== '/').map((modulo) => {
              const Pagina = PAGINAS[modulo.ruta];
              return (
                <Route
                  key={modulo.ruta}
                  element={<RutaProtegida roles={modulo.roles} permiso={modulo.permiso} />}
                >
                  <Route
                    path={modulo.ruta}
                    element={Pagina ? <Pagina /> : <PaginaPendiente modulo={modulo} />}
                  />
                </Route>
              );
            })}
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}