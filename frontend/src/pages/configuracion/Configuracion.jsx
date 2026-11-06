// frontend/src/pages/configuracion/Configuracion.jsx
// Configuración: pestañas según el rol y los permisos del usuario.
// - Mi cuenta (todos): datos de la sesión y cambio de contraseña.
// - Impuestos y margen (permiso "finanzas_gestionar").
// - Suscripción (todos ven el estado; el administrador paga y desbloquea).
// - Dispositivos (solo administrador).
// Los datos del negocio (nombre, NIT, dirección) salen de variables de entorno
// del backend y no tienen endpoint de edición.

import { useEffect, useState } from 'react';
import { CreditCard, Percent, Smartphone, User } from 'lucide-react';

import PanelCuenta from '../../components/configuracion/PanelCuenta.jsx';
import PanelDispositivos from '../../components/configuracion/PanelDispositivos.jsx';
import PanelFinanzas from '../../components/configuracion/PanelFinanzas.jsx';
import PanelSuscripcion from '../../components/configuracion/PanelSuscripcion.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { obtenerEstadoSuscripcion } from '../../services/modules/suscripcionService.js';
import '../../styles/catalogo.css';
import '../../styles/compras.css';

const SECCIONES = [
  { id: 'cuenta', etiqueta: 'Mi cuenta', icono: User, visible: () => true },
  { id: 'finanzas', etiqueta: 'Impuestos y margen', icono: Percent, visible: ({ tienePermiso }) => tienePermiso('finanzas_gestionar') },
  { id: 'suscripcion', etiqueta: 'Suscripción', icono: CreditCard, visible: () => true },
  { id: 'dispositivos', etiqueta: 'Dispositivos', icono: Smartphone, visible: ({ esAdmin }) => esAdmin },
];

export default function Configuracion() {
  const { esAdmin, tienePermiso } = useAuth();
  const [seccion, setSeccion] = useState('cuenta');
  const [suscripcion, setSuscripcion] = useState(null);

  // Bloque: el estado de la suscripción se consulta una vez al abrir la pantalla
  useEffect(() => {
    obtenerEstadoSuscripcion().then(setSuscripcion).catch(() => {});
  }, []);

  const visibles = SECCIONES.filter((s) => s.visible({ esAdmin, tienePermiso }));

  return (
    <div className="catalogo">
      <div className="pestanas" role="tablist" aria-label="Secciones de configuración">
        {visibles.map((s) => {
          const Icono = s.icono;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={seccion === s.id}
              className={`pestana ${seccion === s.id ? 'activa' : ''}`}
              onClick={() => setSeccion(s.id)}
            >
              <Icono size={18} aria-hidden="true" /> {s.etiqueta}
            </button>
          );
        })}
      </div>

      <div role="tabpanel">
        {seccion === 'cuenta' && <PanelCuenta />}
        {seccion === 'finanzas' && <PanelFinanzas />}
        {seccion === 'suscripcion' && <PanelSuscripcion estado={suscripcion} esAdmin={esAdmin} onActualizado={setSuscripcion} />}
        {seccion === 'dispositivos' && <PanelDispositivos />}
      </div>
    </div>
  );
}