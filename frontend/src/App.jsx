// frontend/src/App.jsx
// Define las rutas de la aplicación: login y diagnóstico (públicos), y el resto
// dentro del layout con sidebar, protegido por sesión, rol y permisos.
// Cada pantalla se carga solo cuando se visita (lazy), así la primera carga en
// Vercel es rápida. El layout (menú y encabezado) permanece mientras carga la pantalla.
// La ruta /test se puede ocultar con VITE_HABILITAR_TEST=false.

import { Suspense, lazy, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Toaster, toast } from 'sonner';

import RutaProtegida from './routes/RutaProtegida.jsx';
import { MODULOS } from './routes/navegacion.js';
import LayoutApp from './components/layout/LayoutApp.jsx';
import PaginaPendiente from './components/common/PaginaPendiente.jsx';
import { EVENTO_SISTEMA_BLOQUEADO } from './services/api.js';
import { useAuth } from './context/AuthContext.jsx';

// Bloque: pantallas cargadas bajo demanda
const Login = lazy(() => import('./pages/auth/Login.jsx'));
const Inicio = lazy(() => import('./pages/dashboard/Inicio.jsx'));
const Diagnostico = lazy(() => import('./pages/test/Diagnostico.jsx'));

// Bloque: página de cada módulo, por ruta
const PAGINAS = {
  '/pos': lazy(() => import('./pages/pos/PuntoVenta.jsx')),
  '/mesas': lazy(() => import('./pages/mesas/Mesas.jsx')),
  '/productos': lazy(() => import('./pages/productos/Productos.jsx')),
  '/inventario': lazy(() => import('./pages/inventario/Inventario.jsx')),
  '/categorias': lazy(() => import('./pages/categorias/Categorias.jsx')),
  '/compras': lazy(() => import('./pages/compras/Compras.jsx')),
  '/promociones': lazy(() => import('./pages/promociones/Promociones.jsx')),
  '/reportes': lazy(() => import('./pages/reportes/Reportes.jsx')),
  '/usuarios': lazy(() => import('./pages/usuarios/Usuarios.jsx')),
  '/configuracion': lazy(() => import('./pages/configuracion/Configuracion.jsx')),
};

const TEST_HABILITADO = import.meta.env.VITE_HABILITAR_TEST !== 'false';

// Bloque: indicador mientras se descarga una pantalla
function CargandoPagina() {
  return (
    <div className="estado-vacio" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p className="texto-suave">Cargando…</p>
    </div>
  );
}

// Bloque: envuelve una pantalla perezosa con su indicador de carga
const Perezosa = ({ children }) => <Suspense fallback={<CargandoPagina />}>{children}</Suspense>;

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
        <Route path="/login" element={<RutaPublica><Perezosa><Login /></Perezosa></RutaPublica>} />
        {TEST_HABILITADO && <Route path="/test" element={<Perezosa><Diagnostico /></Perezosa>} />}

        {/* Rutas privadas dentro del layout con sidebar */}
        <Route element={<RutaProtegida />}>
          <Route element={<LayoutApp />}>
            <Route index element={<Perezosa><Inicio /></Perezosa>} />

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
                    element={Pagina ? <Perezosa><Pagina /></Perezosa> : <PaginaPendiente modulo={modulo} />}
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