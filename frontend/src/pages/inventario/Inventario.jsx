// frontend/src/pages/inventario/Inventario.jsx
// Control de existencias: indicadores (productos, unidades, stock bajo, agotados
// y valor del inventario), filtros por estado y categoría, y ajuste manual de
// existencias para quien tiene el permiso "inventario_gestionar". El valor a
// costo solo se muestra a quien puede ver costos.

import { useMemo, useState } from 'react';
import { AlertTriangle, Banknote, Boxes, Layers, PackageX, Pencil, RefreshCw, Search } from 'lucide-react';

import Paginacion from '../../components/common/Paginacion.jsx';
import TarjetaEstadistica from '../../components/common/TarjetaEstadistica.jsx';
import EtiquetaStock from '../../components/productos/EtiquetaStock.jsx';
import ModalAjusteStock from '../../components/productos/ModalAjusteStock.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import useCatalogo from '../../hooks/useCatalogo.js';
import usePaginacion from '../../hooks/usePaginacion.js';
import { formatearCOP, formatearNumero } from '../../utils/formato.js';
import { PRIORIDAD_STOCK, estadoStock } from '../../utils/inventario.js';
import { normalizar } from '../../utils/texto.js';
import '../../styles/catalogo.css';

const ESTADOS = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'agotado', etiqueta: 'Agotados' },
  { valor: 'bajo', etiqueta: 'Stock bajo' },
  { valor: 'ok', etiqueta: 'Disponibles' },
];

export default function Inventario() {
  const { tienePermiso } = useAuth();
  const puedeGestionar = tienePermiso('inventario_gestionar');
  const { productos, categorias, nombreCategoria, cargando, error, recargar } = useCatalogo();

  const [busqueda, setBusqueda] = useState('');
  const [estado, setEstado] = useState('todos');
  const [categoria, setCategoria] = useState('todas');
  const [ajuste, setAjuste] = useState(null);

  // Bloque: indicadores calculados sobre todo el inventario activo
  const resumen = useMemo(() => {
    const conteo = { agotado: 0, bajo: 0, ok: 0 };
    let unidades = 0;
    let valorCosto = 0;
    let valorVenta = 0;
    productos.forEach((p) => {
      conteo[estadoStock(p)] += 1;
      unidades += p.stock_actual;
      valorCosto += p.stock_actual * (p.precio_compra || 0);
      valorVenta += p.stock_actual * p.precio_venta;
    });
    return { conteo, unidades, valorCosto, valorVenta };
  }, [productos]);

  // Bloque: filtra y ordena (lo más urgente primero, luego por nombre)
  const texto = normalizar(busqueda.trim());
  const filtrados = useMemo(
    () =>
      productos
        .filter((p) => {
          if (estado !== 'todos' && estadoStock(p) !== estado) return false;
          if (categoria === 'sin' && p.categoria_id) return false;
          if (typeof categoria === 'number' && p.categoria_id !== categoria) return false;
          if (!texto) return true;
          return [p.nombre, p.codigo_barras].some((valor) => normalizar(valor).includes(texto));
        })
        .sort(
          (a, b) =>
            PRIORIDAD_STOCK[estadoStock(a)] - PRIORIDAD_STOCK[estadoStock(b)] ||
            a.nombre.localeCompare(b.nombre, 'es')
        ),
    [productos, estado, categoria, texto]
  );
  const pag = usePaginacion(filtrados, 12);

  const cambiarCategoria = (evento) => {
    const valor = evento.target.value;
    setCategoria(valor === 'todas' || valor === 'sin' ? valor : Number(valor));
    pag.reiniciar();
  };

  return (
    <div className="catalogo">
      {/* Indicadores */}
      <div className="dash-estadisticas">
        <TarjetaEstadistica titulo="Productos activos" valor={formatearNumero(productos.length)} icono={Boxes} cargando={cargando} />
        <TarjetaEstadistica titulo="Unidades en existencia" valor={formatearNumero(resumen.unidades)} icono={Layers} cargando={cargando} />
        <TarjetaEstadistica
          titulo="Stock bajo"
          valor={formatearNumero(resumen.conteo.bajo)}
          icono={AlertTriangle}
          tono={resumen.conteo.bajo > 0 ? 'rojo' : 'verde'}
          detalle="En o bajo el mínimo"
          cargando={cargando}
        />
        <TarjetaEstadistica
          titulo="Agotados"
          valor={formatearNumero(resumen.conteo.agotado)}
          icono={PackageX}
          tono={resumen.conteo.agotado > 0 ? 'rojo' : 'verde'}
          cargando={cargando}
        />
        <TarjetaEstadistica
          titulo={puedeGestionar ? 'Valor del inventario (costo)' : 'Valor del inventario (venta)'}
          valor={formatearCOP(puedeGestionar ? resumen.valorCosto : resumen.valorVenta)}
          icono={Banknote}
          tono="verde"
          detalle={puedeGestionar ? `A precio de venta: ${formatearCOP(resumen.valorVenta)}` : undefined}
          cargando={cargando}
        />
      </div>

      {/* Filtros */}
      <div className="catalogo-barra">
        <div className="campo-caja">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Buscar por nombre o código…"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              pag.reiniciar();
            }}
            aria-label="Buscar producto"
            maxLength={64}
          />
        </div>
        <select className="filtro-select" value={categoria} onChange={cambiarCategoria} aria-label="Filtrar por categoría">
          <option value="todas">Todas las categorías</option>
          <option value="sin">Sin categoría</option>
          {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => recargar()} aria-label="Actualizar existencias">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
      </div>
      <div className="pos-categorias" role="group" aria-label="Filtrar por estado de existencias">
        {ESTADOS.map((e) => (
          <button
            key={e.valor}
            type="button"
            className={`chip ${estado === e.valor ? 'activo' : ''}`}
            onClick={() => {
              setEstado(e.valor);
              pag.reiniciar();
            }}
          >
            {e.etiqueta}
          </button>
        ))}
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="tarjeta">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 44, marginBottom: 10 }} />)}
        </div>
      ) : filtrados.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Boxes size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>{productos.length === 0 ? 'Aún no hay productos' : 'Sin resultados'}</h2>
          <p className="texto-suave">
            {productos.length === 0 ? 'Registra productos desde el módulo de Productos.' : 'Prueba con otro filtro o búsqueda.'}
          </p>
        </section>
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla-datos">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Categoría</th>
                <th>Existencias</th>
                <th className="num">Mínimo</th>
                <th>Estado</th>
                {puedeGestionar && <th className="num">Valor a costo</th>}
                {puedeGestionar && <th><span className="solo-lectura">Acciones</span></th>}
              </tr>
            </thead>
            <tbody>
              {pag.items.map((p) => {
                const proporcion = Math.min(p.stock_actual / Math.max(p.stock_minimo * 2, 1), 1);
                return (
                  <tr key={p.id}>
                    <td><strong>{p.nombre}</strong></td>
                    <td data-label="Categoría">{nombreCategoria[p.categoria_id] || <span className="texto-suave">Sin categoría</span>}</td>
                    <td data-label="Existencias">
                      <div className="stock-celda">
                        <strong>{formatearNumero(p.stock_actual)}</strong>
                        <span className="stock-barra" aria-hidden="true">
                          <span className={estadoStock(p)} style={{ width: `${Math.max(proporcion * 100, p.stock_actual > 0 ? 6 : 0)}%` }} />
                        </span>
                      </div>
                    </td>
                    <td data-label="Mínimo" className="num">{formatearNumero(p.stock_minimo)}</td>
                    <td data-label="Estado"><EtiquetaStock producto={p} /></td>
                    {puedeGestionar && <td data-label="Valor a costo" className="num">{formatearCOP(p.stock_actual * (p.precio_compra || 0))}</td>}
                    {puedeGestionar && (
                      <td className="celda-acciones">
                        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => setAjuste(p)}>
                          <Pencil size={15} aria-hidden="true" /> Ajustar
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Paginacion pagina={pag.pagina} totalPaginas={pag.totalPaginas} total={pag.total} tamano={pag.tamano} onCambiar={pag.irAPagina} />
        </div>
      )}

      <ModalAjusteStock
        producto={ajuste}
        onCerrar={() => setAjuste(null)}
        onGuardado={() => {
          setAjuste(null);
          recargar(true);
        }}
      />
    </div>
  );
}