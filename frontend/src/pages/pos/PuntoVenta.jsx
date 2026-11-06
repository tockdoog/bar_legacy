// frontend/src/pages/pos/PuntoVenta.jsx
// Punto de venta. Catálogo táctil con búsqueda, filtros por categoría y
// promociones, carrito, cobro con cambio en COP y factura. Admite lector USB,
// cámara y escritura manual de códigos de barras.
// Modos: venta rápida (/pos) o cuenta de una mesa (/pos?venta=ID). En modo mesa
// toma el bloqueo colaborativo: si otro usuario la atiende, se muestra un aviso.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Camera, Loader2, Lock, ReceiptText, RefreshCw, ScanBarcode, Search, ShoppingCart, XCircle } from 'lucide-react';
import { toast } from 'sonner';

import Carrito from '../../components/pos/Carrito.jsx';
import Confirmar from '../../components/common/Confirmar.jsx';
import EscanerCamara, { camaraSoportada } from '../../components/pos/EscanerCamara.jsx';
import ModalCobro from '../../components/pos/ModalCobro.jsx';
import ModalExito from '../../components/pos/ModalExito.jsx';
import TarjetaProducto, { TarjetaPromocion } from '../../components/pos/TarjetaProducto.jsx';
import useBloqueoMesa from '../../hooks/useBloqueoMesa.js';
import useLectorCodigoBarras from '../../hooks/useLectorCodigoBarras.js';
import usePedido from '../../hooks/usePedido.js';
import { mensajeDeError } from '../../services/api.js';
import {
  listarCategorias,
  listarProductos,
  listarPromociones,
  registrarEscaneo,
} from '../../services/modules/catalogoService.js';
import {
  cancelarVenta,
  marcarPendientePago,
  pagarVenta,
  registrarVentaRapida,
} from '../../services/modules/ventasService.js';
import { formatearCOP } from '../../utils/formato.js';
import { normalizar } from '../../utils/texto.js';
import '../../styles/pos.css';

const REGEX_CODIGO = /^[A-Za-z0-9-]{4,64}$/;

export default function PuntoVenta() {
  const [params] = useSearchParams();
  const navegar = useNavigate();
  const ventaParam = params.get('venta');
  const ventaId = /^\d+$/.test(ventaParam || '') ? Number(ventaParam) : null;

  // Bloque: catálogo
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [promociones, setPromociones] = useState([]);
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true);
  const [errorCatalogo, setErrorCatalogo] = useState('');

  // Bloque: filtros y ventanas
  const [busqueda, setBusqueda] = useState('');
  const [filtro, setFiltro] = useState('todos'); // 'todos' | 'promos' | id de categoría
  const [carritoAbierto, setCarritoAbierto] = useState(false);
  const [cobroAbierto, setCobroAbierto] = useState(false);
  const [camaraAbierta, setCamaraAbierta] = useState(false);
  const [ventaCobrada, setVentaCobrada] = useState(null);
  const [confirmacion, setConfirmacion] = useState(null); // 'vaciar' | 'cancelar'
  const [procesando, setProcesando] = useState(false);

  const pedido = usePedido(ventaId, productos);

  // Bloque: bloqueo colaborativo de la mesa mientras se atiende (se libera al cobrar o al salir)
  const bloqueo = useBloqueoMesa(pedido.venta?.mesa_id ?? null, !ventaCobrada);

  // Bloque: carga productos, categorías y promociones; si una falla, las demás siguen
  const cargarCatalogo = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargandoCatalogo(true);
    setErrorCatalogo('');
    const [prod, cat, promo] = await Promise.allSettled([
      listarProductos(),
      listarCategorias(),
      listarPromociones(),
    ]);
    if (prod.status === 'fulfilled') setProductos(prod.value);
    else setErrorCatalogo(mensajeDeError(prod.reason));
    if (cat.status === 'fulfilled') setCategorias(cat.value);
    if (promo.status === 'fulfilled') setPromociones(promo.value);
    setCargandoCatalogo(false);
  }, []);

  useEffect(() => {
    cargarCatalogo();
  }, [cargarCatalogo]);

  // Bloque: nombre de categoría por id y unidades de cada producto en el carrito
  const nombreCategoria = useMemo(
    () => Object.fromEntries(categorias.map((c) => [c.id, c.nombre])),
    [categorias]
  );
  const unidadesPorProducto = useMemo(() => {
    const mapa = {};
    pedido.lineas.forEach((l) => {
      if (l.productoId) mapa[l.productoId] = (mapa[l.productoId] || 0) + l.cantidad;
    });
    return mapa;
  }, [pedido.lineas]);

  // Bloque: productos visibles según búsqueda (nombre o código) y categoría
  const visibles = useMemo(() => {
    const texto = normalizar(busqueda.trim());
    return productos.filter((p) => {
      if (typeof filtro === 'number' && p.categoria_id !== filtro) return false;
      if (!texto) return true;
      return normalizar(p.nombre).includes(texto) || normalizar(p.codigo_barras).includes(texto);
    });
  }, [productos, busqueda, filtro]);

  // Bloque: una lectura de código (lector USB, cámara o escritura manual)
  function manejarCodigo(codigo) {
    const limpio = codigo.trim();
    const producto = productos.find((p) => p.codigo_barras && p.codigo_barras.toLowerCase() === limpio.toLowerCase());
    registrarEscaneo(limpio, Boolean(producto));
    if (!producto) {
      toast.error(`El código ${limpio} no existe en el inventario.`);
      return;
    }
    pedido.agregarProducto(producto);
    toast.success(`${producto.nombre} agregado`, { duration: 1500 });
  }

  const lectorActivo = !cobroAbierto && !ventaCobrada && !camaraAbierta && !confirmacion;
  useLectorCodigoBarras(manejarCodigo, lectorActivo);

  // Bloque: Enter en el buscador; si el texto parece un código de barras, lo trata como tal
  function alTeclearBusqueda(evento) {
    if (evento.key !== 'Enter') return;
    const texto = busqueda.trim();
    const pareceCodigo = REGEX_CODIGO.test(texto) && /\d/.test(texto);
    const existe = productos.some((p) => p.codigo_barras && p.codigo_barras.toLowerCase() === texto.toLowerCase());
    if (existe || (pareceCodigo && /^\d{6,}$/.test(texto))) {
      evento.preventDefault();
      manejarCodigo(texto);
      setBusqueda('');
    }
  }

  // Bloque: cobro. En mesa se paga la cuenta; en venta rápida se crea y cobra de una vez.
  async function confirmarCobro(pagos) {
    const venta = ventaId
      ? await pagarVenta(ventaId, pagos)
      : await registrarVentaRapida(pedido.itemsLocales, pagos);
    pedido.limpiarLocal();
    setCobroAbierto(false);
    setCarritoAbierto(false);
    setVentaCobrada(venta);
    cargarCatalogo(true); // El stock cambió: se refresca en silencio
  }

  const nuevaVenta = () => {
    setVentaCobrada(null);
    if (ventaId) navegar('/mesas');
  };

  // Bloque: pedir la cuenta (solo mesas)
  async function pedirCuenta() {
    setProcesando(true);
    try {
      await marcarPendientePago(ventaId);
      toast.success('Mesa marcada como pendiente de pago.');
    } catch (error) {
      toast.error(mensajeDeError(error));
    } finally {
      setProcesando(false);
    }
  }

  // Bloque: ejecuta la acción destructiva confirmada (vaciar carrito o cancelar cuenta)
  async function ejecutarConfirmacion() {
    if (confirmacion === 'vaciar') {
      pedido.vaciar();
      setConfirmacion(null);
      return;
    }
    setProcesando(true);
    try {
      await cancelarVenta(ventaId);
      toast.success('Cuenta cancelada. La mesa quedó libre.');
      navegar('/mesas');
    } catch (error) {
      toast.error(mensajeDeError(error));
    } finally {
      setProcesando(false);
      setConfirmacion(null);
    }
  }

  // Bloque: estados de carga, error y bloqueo de la cuenta de una mesa
  if (ventaId && (pedido.cargando || bloqueo.situacion === 'verificando')) {
    return (
      <div className="estado-vacio" role="status">
        <Loader2 size={32} className="girar" aria-hidden="true" />
        <p className="texto-suave">{pedido.cargando ? 'Cargando la cuenta…' : 'Verificando la mesa…'}</p>
      </div>
    );
  }
  if (ventaId && pedido.errorCarga) {
    return (
      <section className="tarjeta estado-vacio" role="alert">
        <XCircle size={40} color="var(--rojo)" aria-hidden="true" />
        <h2>No se pudo abrir la cuenta</h2>
        <p className="texto-suave">{pedido.errorCarga}</p>
        <Link to="/mesas" className="boton boton-secundario">Volver a mesas</Link>
      </section>
    );
  }
  if (ventaId && bloqueo.situacion === 'ocupado') {
    return (
      <section className="tarjeta estado-vacio" role="alert">
        <Lock size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
        <h2>Mesa en uso</h2>
        <p className="texto-suave">{bloqueo.mensaje}</p>
        <p className="texto-suave">Si esa persona sale, esta pantalla se habilitará sola.</p>
        <Link to="/mesas" className="boton boton-secundario">Volver a mesas</Link>
      </section>
    );
  }

  const titulo = ventaId ? `Mesa ${pedido.venta?.numero_mesa ?? ''}` : 'Venta rápida';
  const subtitulo = ventaId ? `Cuenta #${ventaId}` : 'Sin mesa asociada';

  return (
    <div className="pos">
      {/* ----- Columna izquierda: catálogo ----- */}
      <section className="pos-catalogo" aria-label="Catálogo de productos">
        <div className="pos-herramientas">
          <div className="campo-caja pos-buscador">
            <Search size={18} aria-hidden="true" />
            <input
              type="search"
              placeholder="Buscar por nombre o escanear código…"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              onKeyDown={alTeclearBusqueda}
              aria-label="Buscar producto"
              maxLength={64}
            />
          </div>
          {camaraSoportada() && (
            <button type="button" className="boton boton-secundario" onClick={() => setCamaraAbierta(true)}>
              <Camera size={18} aria-hidden="true" /> <span className="solo-escritorio">Cámara</span>
            </button>
          )}
          <button type="button" className="boton boton-secundario" onClick={() => cargarCatalogo()} disabled={cargandoCatalogo} aria-label="Actualizar catálogo">
            <RefreshCw size={18} className={cargandoCatalogo ? 'girar' : ''} aria-hidden="true" />
          </button>
        </div>
        <p className="pos-ayuda texto-suave">
          <ScanBarcode size={14} aria-hidden="true" /> Lector USB listo: escanea en cualquier momento.
        </p>

        {/* Filtros por categoría y promociones */}
        <div className="pos-categorias" role="group" aria-label="Filtrar por categoría">
          <button type="button" className={`chip ${filtro === 'todos' ? 'activo' : ''}`} onClick={() => setFiltro('todos')}>Todos</button>
          {promociones.length > 0 && (
            <button type="button" className={`chip ${filtro === 'promos' ? 'activo' : ''}`} onClick={() => setFiltro('promos')}>
              Promociones
            </button>
          )}
          {categorias.map((c) => (
            <button key={c.id} type="button" className={`chip ${filtro === c.id ? 'activo' : ''}`} onClick={() => setFiltro(c.id)}>
              {c.nombre}
            </button>
          ))}
        </div>

        {/* Rejilla de productos o promociones */}
        {cargandoCatalogo ? (
          <div className="pos-productos">
            {Array.from({ length: 8 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 210 }} />)}
          </div>
        ) : errorCatalogo ? (
          <p className="mensaje-error" role="alert">{errorCatalogo}</p>
        ) : filtro === 'promos' ? (
          <div className="pos-productos">
            {promociones.map((promo) => (
              <TarjetaPromocion key={promo.id} promocion={promo} onAgregar={pedido.agregarPromocion} />
            ))}
          </div>
        ) : visibles.length === 0 ? (
          <div className="estado-vacio">
            <Search size={34} color="var(--texto-suave)" aria-hidden="true" />
            <p className="texto-suave">
              {productos.length === 0
                ? 'Aún no hay productos. Agrégalos desde el módulo de Productos.'
                : 'No se encontraron productos con ese criterio.'}
            </p>
          </div>
        ) : (
          <div className="pos-productos">
            {visibles.map((producto) => (
              <TarjetaProducto
                key={producto.id}
                producto={producto}
                categoria={nombreCategoria[producto.categoria_id]}
                enCarrito={unidadesPorProducto[producto.id] || 0}
                onAgregar={pedido.agregarProducto}
              />
            ))}
          </div>
        )}
      </section>

      {/* ----- Columna derecha: carrito (hoja inferior en móvil) ----- */}
      <Carrito
        titulo={titulo}
        subtitulo={subtitulo}
        lineas={pedido.lineas}
        total={pedido.total}
        ocupado={pedido.ocupado || procesando}
        abierto={carritoAbierto}
        onCerrar={() => setCarritoAbierto(false)}
        onCambiar={pedido.cambiarCantidad}
        onQuitar={pedido.quitar}
        onVaciar={() => setConfirmacion('vaciar')}
        onCobrar={() => setCobroAbierto(true)}
        acciones={
          ventaId && (
            <>
              <button type="button" className="boton boton-secundario boton-compacto" onClick={pedirCuenta} disabled={procesando}>
                <ReceiptText size={16} aria-hidden="true" /> Pedir cuenta
              </button>
              <button type="button" className="boton boton-secundario boton-compacto" onClick={() => setConfirmacion('cancelar')} disabled={procesando}>
                <XCircle size={16} aria-hidden="true" /> Cancelar cuenta
              </button>
            </>
          )
        }
      />

      {/* Barra flotante para abrir el carrito en pantallas pequeñas */}
      <button type="button" className="boton boton-primario pos-barra-movil" onClick={() => setCarritoAbierto(true)}>
        <ShoppingCart size={20} aria-hidden="true" />
        <span>{pedido.cantidadTotal} producto(s)</span>
        <strong>{formatearCOP(pedido.total)}</strong>
      </button>

      {/* Ventanas */}
      <ModalCobro abierto={cobroAbierto} total={pedido.total} onCerrar={() => setCobroAbierto(false)} onConfirmar={confirmarCobro} />
      <ModalExito venta={ventaCobrada} onNueva={nuevaVenta} />
      <EscanerCamara abierto={camaraAbierta} onCerrar={() => setCamaraAbierta(false)} onCodigo={manejarCodigo} />
      <Confirmar
        abierto={Boolean(confirmacion)}
        titulo={confirmacion === 'cancelar' ? 'Cancelar cuenta' : 'Vaciar carrito'}
        mensaje={
          confirmacion === 'cancelar'
            ? 'Se cancelará la cuenta sin cobrar y la mesa quedará libre. ¿Deseas continuar?'
            : 'Se quitarán todos los productos del carrito. ¿Deseas continuar?'
        }
        textoConfirmar={confirmacion === 'cancelar' ? 'Cancelar cuenta' : 'Vaciar'}
        peligro
        cargando={procesando}
        onConfirmar={ejecutarConfirmacion}
        onCancelar={() => setConfirmacion(null)}
      />
    </div>
  );
}