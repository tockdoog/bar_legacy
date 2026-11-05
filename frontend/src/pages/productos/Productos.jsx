// frontend/src/pages/productos/Productos.jsx
// Catálogo de productos: tabla con búsqueda, filtro por categoría y paginación;
// en móviles las filas se convierten en tarjetas. Quien tiene el permiso
// "inventario_gestionar" puede crear, editar y eliminar; los demás solo consultan
// y no ven costos (el backend tampoco se los envía).

import { useState } from 'react';
import { Barcode, Package, Pencil, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../../components/common/Confirmar.jsx';
import Paginacion from '../../components/common/Paginacion.jsx';
import EscanerCamara, { camaraSoportada } from '../../components/pos/EscanerCamara.jsx';
import EtiquetaStock from '../../components/productos/EtiquetaStock.jsx';
import FormularioProducto from '../../components/productos/FormularioProducto.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import useCatalogo from '../../hooks/useCatalogo.js';
import usePaginacion from '../../hooks/usePaginacion.js';
import { mensajeDeError, urlImagen } from '../../services/api.js';
import { eliminarProducto } from '../../services/modules/productosService.js';
import { formatearCOP, formatearNumero } from '../../utils/formato.js';
import { normalizar } from '../../utils/texto.js';
import '../../styles/catalogo.css';

export default function Productos() {
  const { tienePermiso } = useAuth();
  const puedeGestionar = tienePermiso('inventario_gestionar');
  const puedeFinanzas = tienePermiso('finanzas_gestionar');

  const { productos, categorias, nombreCategoria, presentaciones, cargando, error, recargar } = useCatalogo();

  const [busqueda, setBusqueda] = useState('');
  const [categoria, setCategoria] = useState('todas'); // 'todas' | 'sin' | id
  const [formulario, setFormulario] = useState({ abierto: false, producto: null });
  const [porEliminar, setPorEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [camara, setCamara] = useState(false);
  const [codigoEscaneado, setCodigoEscaneado] = useState(null);

  // Bloque: filtra por texto (nombre, código o presentación) y por categoría
  const texto = normalizar(busqueda.trim());
  const filtrados = productos.filter((p) => {
    if (categoria === 'sin' && p.categoria_id) return false;
    if (typeof categoria === 'number' && p.categoria_id !== categoria) return false;
    if (!texto) return true;
    return [p.nombre, p.codigo_barras, p.presentacion].some((valor) => normalizar(valor).includes(texto));
  });
  const pag = usePaginacion(filtrados, 10);

  const cambiarCategoria = (evento) => {
    const valor = evento.target.value;
    setCategoria(valor === 'todas' || valor === 'sin' ? valor : Number(valor));
    pag.reiniciar();
  };

  // Bloque: tras guardar, cierra el formulario y refresca la lista sin parpadeo
  const alGuardar = () => {
    setFormulario({ abierto: false, producto: null });
    recargar(true);
  };

  async function confirmarEliminacion() {
    setEliminando(true);
    try {
      await eliminarProducto(porEliminar.id);
      toast.success(`"${porEliminar.nombre}" fue eliminado. Su historial de ventas se conserva.`);
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
      {/* Barra de búsqueda, filtro y acciones */}
      <div className="catalogo-barra">
        <div className="campo-caja">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Buscar por nombre, código o presentación…"
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
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => recargar()} aria-label="Actualizar lista">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        {puedeGestionar && (
          <button type="button" className="boton boton-primario boton-compacto" onClick={() => setFormulario({ abierto: true, producto: null })}>
            <Plus size={18} aria-hidden="true" /> Nuevo producto
          </button>
        )}
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="tarjeta">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 44, marginBottom: 10 }} />)}
        </div>
      ) : filtrados.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Package size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>{productos.length === 0 ? 'Aún no hay productos' : 'Sin resultados'}</h2>
          <p className="texto-suave">
            {productos.length === 0
              ? puedeGestionar
                ? 'Crea el primero con el botón "Nuevo producto".'
                : 'Pídele al administrador que registre los productos.'
              : 'Prueba con otra búsqueda o categoría.'}
          </p>
        </section>
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla-datos">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Código</th>
                <th>Categoría</th>
                <th>Presentación</th>
                {puedeGestionar && <th className="num">Compra</th>}
                <th className="num">Venta</th>
                <th>Existencias</th>
                {puedeGestionar && <th><span className="solo-lectura">Acciones</span></th>}
              </tr>
            </thead>
            <tbody>
              {pag.items.map((p) => {
                const imagen = urlImagen(p.imagen_url);
                return (
                  <tr key={p.id}>
                    <td>
                      <div className="celda-producto">
                        <span className="miniatura">
                          {imagen ? <img src={imagen} alt="" loading="lazy" /> : <Package size={20} aria-hidden="true" />}
                        </span>
                        <strong>{p.nombre}</strong>
                      </div>
                    </td>
                    <td data-label="Código">
                      {p.codigo_barras ? <span className="codigo"><Barcode size={14} aria-hidden="true" /> {p.codigo_barras}</span> : <span className="texto-suave">—</span>}
                    </td>
                    <td data-label="Categoría">{nombreCategoria[p.categoria_id] || <span className="texto-suave">Sin categoría</span>}</td>
                    <td data-label="Presentación">{p.presentacion}</td>
                    {puedeGestionar && <td data-label="Compra" className="num">{formatearCOP(p.precio_compra)}</td>}
                    <td data-label="Venta" className="num"><strong>{formatearCOP(p.precio_venta)}</strong></td>
                    <td data-label="Existencias">
                      <span className="existencias">{formatearNumero(p.stock_actual)} <EtiquetaStock producto={p} /></span>
                    </td>
                    {puedeGestionar && (
                      <td className="celda-acciones">
                        <button type="button" className="boton-icono-borde" onClick={() => setFormulario({ abierto: true, producto: p })} aria-label={`Editar ${p.nombre}`}>
                          <Pencil size={16} />
                        </button>
                        <button type="button" className="boton-icono-borde peligro" onClick={() => setPorEliminar(p)} aria-label={`Eliminar ${p.nombre}`}>
                          <Trash2 size={16} />
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

      {/* Ventanas */}
      <FormularioProducto
        abierto={formulario.abierto}
        producto={formulario.producto}
        categorias={categorias}
        presentaciones={presentaciones}
        puedeFinanzas={puedeFinanzas}
        codigoEscaneado={codigoEscaneado}
        onEscanear={camaraSoportada() ? () => setCamara(true) : null}
        onCerrar={() => setFormulario({ abierto: false, producto: null })}
        onGuardado={alGuardar}
      />
      <EscanerCamara
        abierto={camara}
        onCerrar={() => setCamara(false)}
        onCodigo={(valor) => setCodigoEscaneado({ valor, marca: Date.now() })}
      />
      <Confirmar
        abierto={Boolean(porEliminar)}
        titulo="Eliminar producto"
        mensaje={`¿Eliminar "${porEliminar?.nombre ?? ''}"? Dejará de aparecer en el punto de venta, pero su historial de ventas y compras se conserva.`}
        textoConfirmar="Eliminar"
        peligro
        cargando={eliminando}
        onConfirmar={confirmarEliminacion}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}