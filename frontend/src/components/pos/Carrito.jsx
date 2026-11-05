// frontend/src/components/pos/Carrito.jsx
// Panel del carrito: líneas con control de cantidad, subtotales, total y botones
// de vaciar y cobrar. En móviles se muestra como una hoja inferior deslizante.

import { AnimatePresence, motion } from 'framer-motion';
import { Loader2, Minus, Plus, ShoppingCart, Trash2, X } from 'lucide-react';

import { formatearCOP } from '../../utils/formato.js';

export default function Carrito({
  titulo,
  subtitulo,
  lineas,
  total,
  ocupado,
  abierto,
  acciones,
  onCambiar,
  onQuitar,
  onVaciar,
  onCobrar,
  onCerrar,
}) {
  return (
    <aside className={`tarjeta pos-carrito ${abierto ? 'abierto' : ''}`} aria-label="Carrito de compra">
      {/* Cabecera: identifica la cuenta (venta rápida o mesa) */}
      <div className="carrito-cabecera">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <p className="texto-suave">{subtitulo}</p>}
        </div>
        {ocupado && <Loader2 size={18} className="girar" aria-label="Guardando" />}
        <button type="button" className="boton-icono carrito-cerrar" onClick={onCerrar} aria-label="Cerrar carrito">
          <X size={22} />
        </button>
      </div>

      {acciones && <div className="carrito-acciones">{acciones}</div>}

      {/* Líneas del carrito, con animación al agregar y quitar */}
      {lineas.length === 0 ? (
        <div className="carrito-vacio">
          <ShoppingCart size={34} aria-hidden="true" />
          <p className="texto-suave">El carrito está vacío. Toca un producto o escanea un código de barras.</p>
        </div>
      ) : (
        <ul className="carrito-lista">
          <AnimatePresence initial={false}>
            {lineas.map((linea) => (
              <motion.li
                key={linea.clave}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, x: 30 }}
                transition={{ duration: 0.18 }}
                className="carrito-linea"
              >
                <div className="carrito-info">
                  <strong>{linea.nombre}</strong>
                  <span className="texto-suave">
                    {formatearCOP(linea.precio)} c/u
                    {linea.promocion && <span className="etiqueta ambar">Promo</span>}
                  </span>
                </div>
                <div className="carrito-cantidad">
                  <button type="button" onClick={() => onCambiar(linea, linea.cantidad - 1)} aria-label={`Quitar una unidad de ${linea.nombre}`}>
                    <Minus size={16} />
                  </button>
                  <span aria-live="polite">{linea.cantidad}</span>
                  <button type="button" onClick={() => onCambiar(linea, linea.cantidad + 1)} aria-label={`Agregar una unidad de ${linea.nombre}`}>
                    <Plus size={16} />
                  </button>
                </div>
                <strong className="carrito-subtotal">{formatearCOP(linea.subtotal)}</strong>
                <button type="button" className="boton-icono" onClick={() => onQuitar(linea)} aria-label={`Eliminar ${linea.nombre}`}>
                  <Trash2 size={18} />
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      {/* Total y acciones principales */}
      <div className="carrito-pie">
        <div className="carrito-total">
          <span>Total</span>
          <strong>{formatearCOP(total)}</strong>
        </div>
        <div className="carrito-botones">
          <button type="button" className="boton boton-secundario" onClick={onVaciar} disabled={lineas.length === 0}>
            <Trash2 size={18} aria-hidden="true" /> Vaciar
          </button>
          <button type="button" className="boton boton-primario boton-grande" onClick={onCobrar} disabled={lineas.length === 0 || total <= 0}>
            Cobrar
          </button>
        </div>
      </div>
    </aside>
  );
}