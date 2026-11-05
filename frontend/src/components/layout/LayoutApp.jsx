// frontend/src/components/layout/LayoutApp.jsx
// Estructura general de las pantallas privadas: barra lateral, encabezado,
// aviso de suscripción y el contenido de cada módulo con una transición suave.
// En móviles la barra lateral es un panel deslizante con fondo oscurecido.

import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Lock } from 'lucide-react';

import Sidebar from './Sidebar.jsx';
import Encabezado from './Encabezado.jsx';
import { obtenerEstadoSuscripcion } from '../../services/modules/suscripcionService.js';
import { formatearCOP } from '../../utils/formato.js';
import '../../styles/layout.css';

export default function LayoutApp() {
  const ubicacion = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [suscripcion, setSuscripcion] = useState(null);

  // Bloque: cierra el menú móvil cada vez que se navega a otra pantalla
  useEffect(() => {
    setMenuAbierto(false);
  }, [ubicacion.pathname]);

  // Bloque: consulta el estado de la suscripción al entrar y cada 10 minutos
  useEffect(() => {
    let activo = true;
    const cargar = () =>
      obtenerEstadoSuscripcion()
        .then((datos) => activo && setSuscripcion(datos))
        .catch(() => {});
    cargar();
    const temporizador = setInterval(cargar, 10 * 60 * 1000);
    return () => {
      activo = false;
      clearInterval(temporizador);
    };
  }, []);

  // Bloque: decide si se muestra un aviso (bloqueado, o falta 1 día o menos)
  const mostrarAviso = suscripcion && (suscripcion.bloqueado || suscripcion.dias_restantes <= 1);

  return (
    <div className="app-contenedor">
      <a className="saltar-contenido" href="#contenido">Saltar al contenido</a>

      <Sidebar abierto={menuAbierto} onCerrar={() => setMenuAbierto(false)} />

      {/* Fondo oscurecido que cierra el menú en móviles */}
      <AnimatePresence>
        {menuAbierto && (
          <motion.div
            className="sidebar-fondo"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMenuAbierto(false)}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      <div className="app-principal">
        <Encabezado onAbrirMenu={() => setMenuAbierto(true)} />

        {mostrarAviso && (
          <div
            className={`aviso-suscripcion ${suscripcion.bloqueado ? 'critico' : ''}`}
            role="alert"
          >
            {suscripcion.bloqueado ? <Lock size={18} aria-hidden="true" /> : <AlertTriangle size={18} aria-hidden="true" />}
            <span>
              {suscripcion.mensaje ||
                'La suscripción está próxima a vencer.'}
              {suscripcion.valor_mensual_cop > 0 &&
                ` Valor mensual: ${formatearCOP(suscripcion.valor_mensual_cop)}.`}
            </span>
          </div>
        )}

        <main className="app-contenido" id="contenido" tabIndex={-1}>
          <motion.div
            key={ubicacion.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}