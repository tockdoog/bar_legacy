// frontend/src/components/pos/ModalCobro.jsx
// Cobro en dos pasos: 1) ingresar los pagos (uno o varios métodos, factura
// partida) viendo el recibido y el cambio al instante; 2) resumen final antes
// de confirmar. Valida que el dinero alcance y que el cambio salga de efectivo.

import { useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import { toast } from 'sonner';

import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import { formatearCOP } from '../../utils/formato.js';
import { METODOS_PAGO, aEntero, etiquetaMetodo, evaluarPagos, formatearMiles } from '../../utils/pos.js';

// Bloque: filas de pago con identificador propio para que React las distinga
let contadorFilas = 0;
const nuevaFila = (metodo = 'efectivo', texto = '') => ({ id: ++contadorFilas, metodo, texto });

export default function ModalCobro({ abierto, total, onCerrar, onConfirmar }) {
  const [filas, setFilas] = useState([nuevaFila()]);
  const [paso, setPaso] = useState('pago');
  const [enviando, setEnviando] = useState(false);

  // Bloque: reinicia el formulario cada vez que se abre
  useEffect(() => {
    if (abierto) {
      setFilas([nuevaFila()]);
      setPaso('pago');
      setEnviando(false);
    }
  }, [abierto]);

  // Bloque: pagos válidos (monto mayor a cero) y su evaluación frente al total
  const pagos = useMemo(
    () =>
      filas
        .map((fila) => ({ metodo_pago: fila.metodo, monto: aEntero(fila.texto) }))
        .filter((pago) => pago.monto > 0),
    [filas]
  );
  const evaluacion = useMemo(() => evaluarPagos(pagos, total), [pagos, total]);

  const actualizarFila = (id, cambios) =>
    setFilas((previo) => previo.map((fila) => (fila.id === id ? { ...fila, ...cambios } : fila)));
  const agregarFila = () =>
    setFilas((previo) => [...previo, nuevaFila('nequi', evaluacion.faltante ? String(evaluacion.faltante) : '')]);
  const quitarFila = (id) => setFilas((previo) => previo.filter((fila) => fila.id !== id));

  // Bloque: avanza al resumen solo si los pagos son válidos
  function revisar(evento) {
    evento.preventDefault();
    if (evaluacion.valido) setPaso('resumen');
  }

  // Bloque: envía el cobro; si falla, vuelve al paso de pago mostrando el error
  async function confirmar() {
    setEnviando(true);
    try {
      await onConfirmar(pagos);
    } catch (error) {
      toast.error(mensajeDeError(error));
      setPaso('pago');
    } finally {
      setEnviando(false);
    }
  }

  const mensajeProblema = evaluacion.cambioImposible
    ? 'El cambio solo puede devolverse de lo recibido en efectivo.'
    : '';

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Cobrar venta" ancho={540} bloqueado={enviando}>
      <div className="cobro-total">
        <span>Total a cobrar</span>
        <strong>{formatearCOP(total)}</strong>
      </div>

      {paso === 'pago' ? (
        <form onSubmit={revisar} noValidate>
          {filas.map((fila, indice) => (
            <div className="cobro-fila" key={fila.id}>
              <select
                value={fila.metodo}
                onChange={(e) => actualizarFila(fila.id, { metodo: e.target.value })}
                aria-label={`Método de pago ${indice + 1}`}
              >
                {METODOS_PAGO.map((metodo) => (
                  <option key={metodo.valor} value={metodo.valor}>{metodo.etiqueta}</option>
                ))}
              </select>
              <div className="campo-caja">
                <span aria-hidden="true">$</span>
                <input
                  type="text"
                  inputMode="numeric"
                  autoFocus={indice === 0}
                  placeholder={fila.metodo === 'efectivo' ? 'Dinero recibido' : 'Monto'}
                  value={formatearMiles(aEntero(fila.texto))}
                  onChange={(e) => actualizarFila(fila.id, { texto: String(aEntero(e.target.value) || '') })}
                  aria-label={`Monto del método ${indice + 1}`}
                />
              </div>
              {filas.length > 1 && (
                <button type="button" className="boton-icono" onClick={() => quitarFila(fila.id)} aria-label="Quitar este pago">
                  <X size={18} />
                </button>
              )}
            </div>
          ))}

          {/* Atajos de dinero recibido: solo cuando hay un único pago en efectivo */}
          {filas.length === 1 && filas[0].metodo === 'efectivo' && (
            <div className="cobro-atajos">
              <button type="button" onClick={() => actualizarFila(filas[0].id, { texto: String(evaluacion.totalEntero) })}>
                Exacto
              </button>
              {[10000, 20000, 50000, 100000]
                .filter((valor) => valor >= evaluacion.totalEntero)
                .slice(0, 3)
                .map((valor) => (
                  <button key={valor} type="button" onClick={() => actualizarFila(filas[0].id, { texto: String(valor) })}>
                    {formatearCOP(valor)}
                  </button>
                ))}
            </div>
          )}

          {filas.length < 6 && (
            <button type="button" className="boton boton-secundario boton-compacto" onClick={agregarFila}>
              <Plus size={16} aria-hidden="true" /> Dividir pago
            </button>
          )}

          {/* Resumen en vivo: recibido y cambio o faltante */}
          <dl className="cobro-resumen" aria-live="polite">
            <div><dt>Recibido</dt><dd>{formatearCOP(evaluacion.recibido)}</dd></div>
            {evaluacion.faltante > 0 ? (
              <div className="faltante"><dt>Falta</dt><dd>{formatearCOP(evaluacion.faltante)}</dd></div>
            ) : (
              <div className="cambio"><dt>Cambio a devolver</dt><dd>{formatearCOP(evaluacion.cambio)}</dd></div>
            )}
          </dl>
          {mensajeProblema && <p className="mensaje-error" role="alert">{mensajeProblema}</p>}

          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={onCerrar}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={!evaluacion.valido}>
              Revisar y confirmar
            </button>
          </div>
        </form>
      ) : (
        <>
          {/* Paso 2: resumen final antes de confirmar */}
          <ul className="cobro-lista">
            {pagos.map((pago, indice) => (
              <li key={`${pago.metodo_pago}-${indice}`}>
                <span>{etiquetaMetodo(pago.metodo_pago)}</span>
                <strong>{formatearCOP(pago.monto)}</strong>
              </li>
            ))}
          </ul>
          <dl className="cobro-resumen">
            <div><dt>Total</dt><dd>{formatearCOP(total)}</dd></div>
            <div><dt>Recibido</dt><dd>{formatearCOP(evaluacion.recibido)}</dd></div>
            <div className="cambio"><dt>Cambio a devolver</dt><dd>{formatearCOP(evaluacion.cambio)}</dd></div>
          </dl>
          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={() => setPaso('pago')} disabled={enviando}>
              Volver
            </button>
            <button type="button" className="boton boton-primario" onClick={confirmar} disabled={enviando}>
              {enviando && <Loader2 size={18} className="girar" aria-hidden="true" />}
              Confirmar cobro
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}