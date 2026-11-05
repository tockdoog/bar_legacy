// frontend/src/components/compras/PanelCompras.jsx
// Pestaña de compras: historial con filtros (texto y rango de fechas),
// indicadores del periodo filtrado, detalle de cada compra y registro de
// compras nuevas. Los filtros se aplican en el cliente (el backend no filtra).

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Banknote, Eye, Plus, Receipt, RefreshCw, Search, ShoppingBag } from 'lucide-react';

import Paginacion from '../common/Paginacion.jsx';
import TarjetaEstadistica from '../common/TarjetaEstadistica.jsx';
import DetalleCompra from './DetalleCompra.jsx';
import FormularioCompra from './FormularioCompra.jsx';
import usePaginacion from '../../hooks/usePaginacion.js';
import { mensajeDeError } from '../../services/api.js';
import { listarProductos } from '../../services/modules/catalogoService.js';
import { listarCompras } from '../../services/modules/comprasService.js';
import { formatearCOP, formatearFecha, formatearNumero, hoyBogota } from '../../utils/formato.js';
import { normalizar } from '../../utils/texto.js';

export default function PanelCompras({ proveedores, onIrAProveedores }) {
  const [compras, setCompras] = useState([]);
  const [productos, setProductos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [busqueda, setBusqueda] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [formularioAbierto, setFormularioAbierto] = useState(false);
  const [detalle, setDetalle] = useState(null);

  // Bloque: carga compras y productos en paralelo; si falla una, la otra sigue
  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    const [resCompras, resProductos] = await Promise.allSettled([listarCompras(), listarProductos()]);
    if (resCompras.status === 'fulfilled') {
      setCompras(resCompras.value);
      setError('');
    } else {
      setError(mensajeDeError(resCompras.reason));
    }
    if (resProductos.status === 'fulfilled') setProductos(resProductos.value);
    setCargando(false);
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Bloque: filtra por proveedor o producto y por rango de fechas (AAAA-MM-DD, hora de Bogotá)
  const texto = normalizar(busqueda.trim());
  const filtradas = useMemo(
    () =>
      compras.filter((c) => {
        const dia = String(c.fecha).slice(0, 10);
        if (desde && dia < desde) return false;
        if (hasta && dia > hasta) return false;
        if (!texto) return true;
        return (
          normalizar(c.nombre_proveedor).includes(texto) ||
          c.detalles.some((d) => normalizar(d.nombre_producto).includes(texto))
        );
      }),
    [compras, texto, desde, hasta]
  );
  const pag = usePaginacion(filtradas, 10);

  const totalFiltrado = filtradas.reduce((suma, c) => suma + c.total, 0);
  const hayProveedores = proveedores.length > 0;

  return (
    <div className="catalogo">
      {/* Indicadores del periodo filtrado */}
      <div className="dash-estadisticas">
        <TarjetaEstadistica titulo="Compras" valor={formatearNumero(filtradas.length)} icono={Receipt} detalle="Según los filtros" cargando={cargando} />
        <TarjetaEstadistica titulo="Total comprado" valor={formatearCOP(totalFiltrado)} icono={Banknote} tono="verde" detalle="Según los filtros" cargando={cargando} />
      </div>

      {/* Filtros y acciones */}
      <div className="catalogo-barra">
        <div className="campo-caja">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Buscar por proveedor o producto…"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              pag.reiniciar();
            }}
            aria-label="Buscar compra"
            maxLength={64}
          />
        </div>
        <label className="filtro-fecha">
          <span className="texto-suave">Desde</span>
          <input type="date" className="filtro-select" value={desde} max={hasta || hoyBogota()} onChange={(e) => { setDesde(e.target.value); pag.reiniciar(); }} />
        </label>
        <label className="filtro-fecha">
          <span className="texto-suave">Hasta</span>
          <input type="date" className="filtro-select" value={hasta} min={desde || undefined} max={hoyBogota()} onChange={(e) => { setHasta(e.target.value); pag.reiniciar(); }} />
        </label>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => cargar()} aria-label="Actualizar compras">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        <button type="button" className="boton boton-primario boton-compacto" onClick={() => setFormularioAbierto(true)} disabled={!hayProveedores}>
          <Plus size={18} aria-hidden="true" /> Registrar compra
        </button>
      </div>

      {!hayProveedores && !cargando && (
        <p className="aviso-form">
          Para registrar una compra primero necesitas un proveedor.{' '}
          <button type="button" className="enlace-boton" onClick={onIrAProveedores}>Ir a proveedores</button>
        </p>
      )}

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="tarjeta">
          {Array.from({ length: 5 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 44, marginBottom: 10 }} />)}
        </div>
      ) : filtradas.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <ShoppingBag size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>{compras.length === 0 ? 'Aún no hay compras registradas' : 'Sin resultados'}</h2>
          <p className="texto-suave">
            {compras.length === 0 ? 'Cuando registres compras a proveedores aparecerán aquí.' : 'Prueba con otros filtros.'}
          </p>
        </section>
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla-datos">
            <thead>
              <tr>
                <th>Compra</th>
                <th>Fecha</th>
                <th>Proveedor</th>
                <th>Productos</th>
                <th className="num">Total</th>
                <th><span className="solo-lectura">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {pag.items.map((c) => {
                const unidades = c.detalles.reduce((suma, d) => suma + d.cantidad, 0);
                return (
                  <tr key={c.id}>
                    <td><strong>#{c.id}</strong></td>
                    <td data-label="Fecha">{formatearFecha(c.fecha)}</td>
                    <td data-label="Proveedor">{c.nombre_proveedor}</td>
                    <td data-label="Productos">{c.detalles.length} línea(s) · {formatearNumero(unidades)} u.</td>
                    <td data-label="Total" className="num"><strong>{formatearCOP(c.total)}</strong></td>
                    <td className="celda-acciones">
                      <button type="button" className="boton boton-secundario boton-compacto" onClick={() => setDetalle(c)}>
                        <Eye size={15} aria-hidden="true" /> Ver
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Paginacion pagina={pag.pagina} totalPaginas={pag.totalPaginas} total={pag.total} tamano={pag.tamano} onCambiar={pag.irAPagina} />
        </div>
      )}

      <FormularioCompra
        abierto={formularioAbierto}
        proveedores={proveedores}
        productos={productos}
        onCerrar={() => setFormularioAbierto(false)}
        onRegistrada={() => {
          setFormularioAbierto(false);
          cargar(true);
        }}
      />
      <DetalleCompra compra={detalle} onCerrar={() => setDetalle(null)} />
    </div>
  );
}