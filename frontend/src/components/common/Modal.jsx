// frontend/src/components/common/Modal.jsx
// Ventana modal accesible: se cierra con Escape o al hacer clic fuera (salvo que
// esté "bloqueado"), bloquea el scroll del fondo, enfoca el diálogo al abrir y
// devuelve el foco al cerrar. Anima su apertura y cierre.

import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';

import '../../styles/componentes.css';

export default function Modal({ abierto, onCerrar, titulo, children, ancho = 520, bloqueado = false }) {
  const dialogo = useRef(null);
  const cerrar = useRef(onCerrar);
  cerrar.current = onCerrar;

  // Bloque: bloqueo de scroll, foco y cierre con Escape mientras está abierto
  useEffect(() => {
    if (!abierto) return undefined;
    const previo = document.activeElement;
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogo.current?.focus();

    const alTeclear = (evento) => {
      if (evento.key === 'Escape' && !bloqueado) cerrar.current();
    };
    document.addEventListener('keydown', alTeclear);

    return () => {
      document.removeEventListener('keydown', alTeclear);
      document.body.style.overflow = overflowPrevio;
      previo?.focus?.();
    };
  }, [abierto, bloqueado]);

  return (
    <AnimatePresence>
      {abierto && (
        <motion.div
          className="modal-fondo"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(evento) => {
            if (evento.target === evento.currentTarget && !bloqueado) cerrar.current();
          }}
        >
          <motion.div
            ref={dialogo}
            className="modal-caja"
            style={{ maxWidth: ancho }}
            role="dialog"
            aria-modal="true"
            aria-label={titulo}
            tabIndex={-1}
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <div className="modal-cabecera">
              <h2>{titulo}</h2>
              {!bloqueado && (
                <button type="button" className="boton-icono" onClick={onCerrar} aria-label="Cerrar">
                  <X size={22} />
                </button>
              )}
            </div>
            <div className="modal-cuerpo">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}