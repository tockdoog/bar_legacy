// frontend/src/components/layout/Sidebar.jsx
// Barra lateral de navegación. Muestra solo los módulos que el usuario puede
// ver, resalta el módulo actual y se adapta al dispositivo:
// escritorio (completa), tablet (solo iconos) y móvil (panel deslizante).

import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { X } from 'lucide-react';

import { MODULOS, puedeVerModulo } from '../../routes/navegacion.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { urlApi } from '../../services/api.js';

export default function Sidebar({ abierto, onCerrar }) {
  const { esAdmin, tienePermiso } = useAuth();
  const [logoDisponible, setLogoDisponible] = useState(true);

  // Bloque: módulos visibles según el rol y los permisos del usuario
  const visibles = MODULOS.filter((modulo) => puedeVerModulo(modulo, { esAdmin, tienePermiso }));

  return (
    <aside className={`sidebar ${abierto ? 'abierto' : ''}`} aria-label="Navegación principal">
      {/* Marca del negocio y botón de cierre (solo visible en móvil) */}
      <div className="sidebar-marca">
        {logoDisponible && (
          <img
            src={`${urlApi}/imagenes/logo.png`}
            alt=""
            width="36"
            height="36"
            onError={() => setLogoDisponible(false)}
          />
        )}
        <span className="titulo-marca sidebar-texto-marca">
          Bar <span>Legacy</span>
        </span>
        <button type="button" className="boton-icono sidebar-cerrar" onClick={onCerrar} aria-label="Cerrar menú">
          <X size={22} />
        </button>
      </div>

      {/* Lista de módulos; NavLink marca la ruta activa con aria-current */}
      <nav>
        <ul className="sidebar-lista">
          {visibles.map((modulo) => {
            const Icono = modulo.icono;
            return (
              <li key={modulo.ruta}>
                <NavLink
                  to={modulo.ruta}
                  end={modulo.ruta === '/'}
                  title={modulo.etiqueta}
                  onClick={onCerrar}
                  className={({ isActive }) => `sidebar-enlace ${isActive ? 'activo' : ''}`}
                >
                  <Icono size={20} aria-hidden="true" />
                  <span>{modulo.etiqueta}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}