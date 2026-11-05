// frontend/src/components/compras/PanelProveedores.jsx
// Pestaña de proveedores: tabla con búsqueda y paginación, alta, edición y
// eliminación con confirmación. El backend impide eliminar un proveedor que ya
// tiene compras registradas, y ese mensaje se muestra al usuario.

import { useState } from 'react';
import { Pencil, Phone, Plus, RefreshCw, Search, Trash2, Truck } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../common/Confirmar.jsx';
import Paginacion from '../common/Paginacion.jsx';
import FormularioProveedor from './FormularioProveedor.jsx';
import usePaginacion from '../../hooks/usePaginacion.js';
import { mensajeDeError } from '../../services/api.js';
import { eliminarProveedor } from '../../services/modules/proveedoresService.js';
import { etiquetaCanal } from '../../utils/proveedores.js';
import { normalizar } from '../../utils/texto.js';

export default function PanelProveedores({ proveedores, cargando, error, recargar }) {
  const [busqueda, setBusqueda] = useState('');
  const [formulario, setFormulario] = useState({ abierto: false, proveedor: null });
  const [porEliminar, setPorEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);

  // Bloque: filtra por nombre, teléfono, canal o notas
  const texto = normalizar(busqueda.trim());
  const filtrados = proveedores.filter(
    (p) => !texto || [p.nombre, p.telefono, p.notas, etiquetaCanal(p.canal)].some((v) => normalizar(v).includes(texto))
  );
  const pag = usePaginacion(filtrados, 10);

  const alGuardar = () => {
    setFormulario({ abierto: false, proveedor: null });
    recargar(true);
  };

  async function confirmarEliminacion() {
    setEliminando(true);
    try {
      await eliminarProveedor(porEliminar.id);
      toast.success(`Proveedor "${porEliminar.nombre}" eliminado.`);
      recargar(true);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setEliminando(false);
      setPorEliminar(null);
    }
  }

  return (
    <div className="catalogo">
      <div className="catalogo-barra">
        <div className="campo-caja">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Buscar proveedor…"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              pag.reiniciar();
            }}
            aria-label="Buscar proveedor"
            maxLength={64}
          />
        </div>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => recargar()} aria-label="Actualizar proveedores">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        <button type="button" className="boton boton-primario boton-compacto" onClick={() => setFormulario({ abierto: true, proveedor: null })}>
          <Plus size={18} aria-hidden="true" /> Nuevo proveedor
        </button>
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="tarjeta">
          {Array.from({ length: 4 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 44, marginBottom: 10 }} />)}
        </div>
      ) : filtrados.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Truck size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>{proveedores.length === 0 ? 'Aún no hay proveedores' : 'Sin resultados'}</h2>
          <p className="texto-suave">
            {proveedores.length === 0 ? 'Registra el primero para poder anotar compras.' : 'Prueba con otra búsqueda.'}
          </p>
        </section>
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla-datos">
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Canal</th>
                <th>Teléfono</th>
                <th>Notas</th>
                <th><span className="solo-lectura">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {pag.items.map((p) => (
                <tr key={p.id}>
                  <td><strong>{p.nombre}</strong></td>
                  <td data-label="Canal"><span className="etiqueta gris">{etiquetaCanal(p.canal)}</span></td>
                  <td data-label="Teléfono">
                    {p.telefono ? (
                      <a className="enlace-telefono" href={`tel:${p.telefono.replace(/[^\d+]/g, '')}`}>
                        <Phone size={14} aria-hidden="true" /> {p.telefono}
                      </a>
                    ) : <span className="texto-suave">—</span>}
                  </td>
                  <td data-label="Notas">{p.notas || <span className="texto-suave">—</span>}</td>
                  <td className="celda-acciones">
                    <button type="button" className="boton-icono-borde" onClick={() => setFormulario({ abierto: true, proveedor: p })} aria-label={`Editar ${p.nombre}`}>
                      <Pencil size={16} />
                    </button>
                    <button type="button" className="boton-icono-borde peligro" onClick={() => setPorEliminar(p)} aria-label={`Eliminar ${p.nombre}`}>
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Paginacion pagina={pag.pagina} totalPaginas={pag.totalPaginas} total={pag.total} tamano={pag.tamano} onCambiar={pag.irAPagina} />
        </div>
      )}

      <FormularioProveedor
        abierto={formulario.abierto}
        proveedor={formulario.proveedor}
        onCerrar={() => setFormulario({ abierto: false, proveedor: null })}
        onGuardado={alGuardar}
      />
      <Confirmar
        abierto={Boolean(porEliminar)}
        titulo="Eliminar proveedor"
        mensaje={`¿Eliminar a "${porEliminar?.nombre ?? ''}"? Solo es posible si no tiene compras registradas.`}
        textoConfirmar="Eliminar"
        peligro
        cargando={eliminando}
        onConfirmar={confirmarEliminacion}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}