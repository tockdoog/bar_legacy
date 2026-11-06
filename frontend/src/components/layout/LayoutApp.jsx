// frontend/src/components/layout/LayoutApp.jsx
// Estructura general de las pantallas privadas: barra lateral, encabezado,
// aviso de suscripción y el contenido de cada módulo con una transición suave.
// En móviles la barra lateral es un panel deslizante con fondo oscurecido.
//
// CAMBIOS: si la suscripción está bloqueada se muestra la pantalla de bloqueo en
// lugar del módulo, y el estado se vuelve a consultar al recibir un 423.

import { useCallback, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';

import Sidebar from './Sidebar.jsx';
import Encabezado from './Encabezado.jsx';
import PantallaBloqueo from './PantallaBloqueo.jsx';
import { EVENTO_SISTEMA_BLOQUEADO } from '../../services/api.js';
import { obtenerEstadoSuscripcion } from '../../services/modules/suscripcionService.js';
import { formatearCOP } from '../../utils/formato.js';
import '../../styles/layout.css';
import '../../styles/administracion.css';

export default function LayoutApp() {
  const ubicacion = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [suscripcion, setSuscripcion] = useState(null);

  // Bloque: cierra el menú móvil cada vez que se navega a otra pantalla
  useEffect(() => {
    setMenuAbierto(false);
  }, [ubicacion.pathname]);

  // Bloque: consulta el estado de la suscripción al entrar, cada 10 minutos y cuando el backend responde 423
  const cargarEstado = useCallback(() => {
    obtenerEstadoSuscripcion()
      .then(setSuscripcion)
      .catch(() => {});
  }, []);

  useEffect(() => {
    cargarEstado();
    const temporizador = setInterval(cargarEstado, 10 * 60 * 1000);
    window.addEventListener(EVENTO_SISTEMA_BLOQUEADO, cargarEstado);
    return () => {
      clearInterval(temporizador);
      window.removeEventListener(EVENTO_SISTEMA_BLOQUEADO, cargarEstado);
    };
  }, [cargarEstado]);

  const bloqueado = Boolean(suscripcion?.bloqueado);
  const avisoProximo = suscripcion && !bloqueado && suscripcion.dias_restantes <= 1;

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

        {avisoProximo && (
          <div className="aviso-suscripcion" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <span>
              {suscripcion.mensaje || 'La suscripción está próxima a vencer.'}
              {suscripcion.valor_mensual_cop > 0 && ` Valor mensual: ${formatearCOP(suscripcion.valor_mensual_cop)}.`}
            </span>
          </div>
        )}

        <main className="app-contenido" id="contenido" tabIndex={-1}>
          <motion.div
            key={bloqueado ? 'bloqueo' : ubicacion.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            {bloqueado ? <PantallaBloqueo estado={suscripcion} onActualizado={setSuscripcion} /> : <Outlet />}
          </motion.div>
        </main>
      </div>
    </div>
  );
}