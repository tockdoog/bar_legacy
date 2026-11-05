// frontend/src/components/productos/ModalAjusteStock.jsx
// Ajuste manual de existencias de un producto (conteo físico, merma, corrección).
// Muestra la diferencia frente a lo registrado antes de guardar. Para reponer
// mercancía comprada a un proveedor se usa el módulo de Compras.

import { useEffect, useState } from 'react';
import { Loader2, Minus, Plus } from 'lucide-react';
import { toast } from 'sonner';

import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import { actualizarProducto } from '../../services/modules/productosService.js';

const MAXIMO = 1000000;

export default function ModalAjusteStock({ producto, onCerrar, onGuardado }) {
  const [cantidad, setCantidad] = useState('0');
  const [guardando, setGuardando] = useState(false);

  // Bloque: al abrir, parte de las existencias registradas
  useEffect(() => {
    if (producto) setCantidad(String(producto.stock_actual));
  }, [producto]);

  const nueva = Number.parseInt(cantidad, 10);
  const valida = Number.isInteger(nueva) && nueva >= 0 && nueva <= MAXIMO;
  const diferencia = valida && producto ? nueva - producto.stock_actual : 0;

  // Bloque: suma o resta sin bajar de cero
  const mover = (delta) => setCantidad(String(Math.max((valida ? nueva : 0) + delta, 0)));

  async function guardar(evento) {
    evento.preventDefault();
    if (!valida || diferencia === 0) return;
    setGuardando(true);
    try {
      await actualizarProducto(producto.id, { stock_actual: nueva });
      toast.success(`Existencias de "${producto.nombre}" actualizadas.`);
      onGuardado();
    } catch (error) {
      toast.error(mensajeDeError(error));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal abierto={Boolean(producto)} onCerrar={onCerrar} titulo="Ajustar existencias" ancho={440} bloqueado={guardando}>
      {producto && (
        <form onSubmit={guardar} noValidate>
          <p><strong>{producto.nombre}</strong></p>
          <p className="texto-suave">Existencias registradas: {producto.stock_actual}</p>

          <div className="ajuste-controles">
            <button type="button" className="boton boton-secundario boton-compacto" onClick={() => mover(-10)} aria-label="Restar 10">−10</button>
            <button type="button" className="boton boton-secundario boton-compacto" onClick={() => mover(-1)} aria-label="Restar 1"><Minus size={16} /></button>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              max={MAXIMO}
              value={cantidad}
              onChange={(e) => setCantidad(e.target.value)}
              aria-label="Nueva cantidad de existencias"
              autoFocus
            />
            <button type="button" className="boton boton-secundario boton-compacto" onClick={() => mover(1)} aria-label="Sumar 1"><Plus size={16} /></button>
            <button type="button" className="boton boton-secundario boton-compacto" onClick={() => mover(10)} aria-label="Sumar 10">+10</button>
          </div>

          {!valida ? (
            <p className="mensaje-error" role="alert">Ingresa un número entero entre 0 y {MAXIMO.toLocaleString('es-CO')}.</p>
          ) : (
            <p className="texto-suave" aria-live="polite">
              {diferencia === 0
                ? 'Sin cambios.'
                : `Cambio: ${diferencia > 0 ? '+' : ''}${diferencia} unidad(es).`}
            </p>
          )}

          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={guardando || !valida || diferencia === 0}>
              {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />} Guardar ajuste
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}