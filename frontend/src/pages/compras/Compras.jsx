// frontend/src/pages/compras/Compras.jsx
// Módulo de Compras y proveedores: dos pestañas (compras y proveedores) que
// comparten la lista de proveedores. Requiere el permiso "compras_gestionar"
// (lo valida la ruta y, de nuevo, el backend en cada petición).

import { useState } from 'react';
import { ShoppingBag, Truck } from 'lucide-react';

import PanelCompras from '../../components/compras/PanelCompras.jsx';
import PanelProveedores from '../../components/compras/PanelProveedores.jsx';
import useProveedores from '../../hooks/useProveedores.js';
import '../../styles/catalogo.css';
import '../../styles/compras.css';

const PESTANAS = [
  { id: 'compras', etiqueta: 'Compras', icono: ShoppingBag },
  { id: 'proveedores', etiqueta: 'Proveedores', icono: Truck },
];

export default function Compras() {
  const [pestana, setPestana] = useState('compras');
  const proveedores = useProveedores();

  return (
    <div className="catalogo">
      {/* Pestañas accesibles: flechas izquierda y derecha no hacen falta, cada una es un botón */}
      <div className="pestanas" role="tablist" aria-label="Secciones de compras">
        {PESTANAS.map((p) => {
          const Icono = p.icono;
          return (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={pestana === p.id}
              className={`pestana ${pestana === p.id ? 'activa' : ''}`}
              onClick={() => setPestana(p.id)}
            >
              <Icono size={18} aria-hidden="true" /> {p.etiqueta}
            </button>
          );
        })}
      </div>

      <div role="tabpanel">
        {pestana === 'compras' ? (
          <PanelCompras proveedores={proveedores.proveedores} onIrAProveedores={() => setPestana('proveedores')} />
        ) : (
          <PanelProveedores
            proveedores={proveedores.proveedores}
            cargando={proveedores.cargando}
            error={proveedores.error}
            recargar={proveedores.recargar}
          />
        )}
      </div>
    </div>
  );
}