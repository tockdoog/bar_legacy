// frontend/src/components/layout/PantallaBloqueo.jsx
// Pantalla que reemplaza el contenido cuando la suscripción venció (el backend
// responde 423 en casi toda la API). El administrador ve cómo pagar y puede
// desbloquear; los demás usuarios ven un aviso para contactarlo.

import { Lock } from 'lucide-react';

import PanelSuscripcion from '../configuracion/PanelSuscripcion.jsx';
import { useAuth } from '../../context/AuthContext.jsx';

export default function PantallaBloqueo({ estado, onActualizado }) {
  const { esAdmin } = useAuth();

  return (
    <div className="bloqueo-pantalla" role="alert">
      <section className="tarjeta bloqueo-encabezado">
        <Lock size={40} color="var(--rojo)" aria-hidden="true" />
        <h2>Sistema bloqueado por falta de pago</h2>
        <p className="texto-suave">
          {esAdmin
            ? 'Realiza el pago con alguno de los medios de abajo e ingresa la clave que te entregue el proveedor.'
            : 'Avísale al administrador del negocio para que renueve la suscripción.'}
        </p>
      </section>
      <PanelSuscripcion estado={estado} esAdmin={esAdmin} onActualizado={onActualizado} />
    </div>
  );
}