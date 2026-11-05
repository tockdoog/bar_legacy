// frontend/src/components/pos/TarjetaProducto.jsx
// Tarjetas táctiles del catálogo del POS: una para productos y otra para
// promociones. Muestran imagen (si existe), nombre, categoría, presentación,
// precio y disponibilidad. Un producto agotado no se puede seleccionar.

import { Package, Percent } from 'lucide-react';

import { urlImagen } from '../../services/api.js';
import { formatearCOP } from '../../utils/formato.js';

// Bloque: tarjeta de producto
export default function TarjetaProducto({ producto, categoria, enCarrito, onAgregar }) {
  const agotado = producto.stock_actual <= 0;
  const bajo = !agotado && producto.stock_actual <= producto.stock_minimo;
  const imagen = urlImagen(producto.imagen_url);

  return (
    <button
      type="button"
      className={`producto-tarjeta ${agotado ? 'agotado' : ''}`}
      onClick={() => onAgregar(producto)}
      disabled={agotado}
      aria-label={`Agregar ${producto.nombre}, ${formatearCOP(producto.precio_venta)}`}
    >
      <span className="producto-imagen">
        {imagen ? <img src={imagen} alt="" loading="lazy" /> : <Package size={34} aria-hidden="true" />}
        {enCarrito > 0 && <span className="producto-contador">{enCarrito}</span>}
      </span>
      <span className="producto-cuerpo">
        <strong className="producto-nombre">{producto.nombre}</strong>
        <span className="texto-suave producto-detalle">
          {[categoria, producto.presentacion].filter(Boolean).join(' · ')}
        </span>
        <span className="producto-precio">{formatearCOP(producto.precio_venta)}</span>
        <span className={`etiqueta ${agotado ? 'rojo' : bajo ? 'ambar' : 'verde'}`}>
          {agotado ? 'Agotado' : `${producto.stock_actual} disp.`}
        </span>
      </span>
    </button>
  );
}

// Bloque: tarjeta de promoción (combo). No muestra costos ni ganancia.
export function TarjetaPromocion({ promocion, onAgregar }) {
  return (
    <button
      type="button"
      className="producto-tarjeta promocion"
      onClick={() => onAgregar(promocion)}
      aria-label={`Agregar promoción ${promocion.nombre}, ${formatearCOP(promocion.precio_promocional)}`}
    >
      <span className="producto-imagen">
        <Percent size={34} aria-hidden="true" />
      </span>
      <span className="producto-cuerpo">
        <strong className="producto-nombre">{promocion.nombre}</strong>
        <span className="texto-suave producto-detalle">
          {promocion.componentes.map((c) => `${c.cantidad}x ${c.nombre_producto}`).join(' + ')}
        </span>
        <span className="producto-precio">{formatearCOP(promocion.precio_promocional)}</span>
        {promocion.ahorro_cliente > 0 && (
          <span className="etiqueta verde">Ahorra {formatearCOP(promocion.ahorro_cliente)}</span>
        )}
      </span>
    </button>
  );
}