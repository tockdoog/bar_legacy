// frontend/src/components/common/PaginaPendiente.jsx
// Pantalla temporal para los módulos que todavía no se construyen. Se
// reemplaza por la pantalla real de cada módulo en la Fase 4.

import { Link } from 'react-router-dom';
import { Hammer } from 'lucide-react';

export default function PaginaPendiente({ modulo }) {
  const Icono = modulo?.icono || Hammer;

  return (
    <section className="tarjeta estado-vacio" aria-live="polite">
      <Icono size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
      <h2>{modulo?.etiqueta || 'Módulo'} en construcción</h2>
      <p className="texto-suave">Esta pantalla se desarrollará en la siguiente fase del proyecto.</p>
      <Link to="/" className="boton boton-secundario">Volver al Dashboard</Link>
    </section>
  );
}