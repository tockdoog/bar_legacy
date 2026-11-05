// frontend/src/pages/mesas/Mesas.jsx
// Plano visual de mesas: libre (verde), ocupada (dorado) y pendiente de pago
// (rojo), con total acumulado y tiempo de ocupación tomados de las ventas
// abiertas. Se actualiza solo cada 10 segundos. El administrador puede crear y
// eliminar mesas libres. Abrir o consultar una mesa lleva al POS.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Armchair, Clock, Loader2, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../../components/common/Confirmar.jsx';
import Modal from '../../components/common/Modal.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { mensajeDeError } from '../../services/api.js';
import { crearMesa, eliminarMesa, listarMesas } from '../../services/modules/mesasService.js';
import { abrirVenta, listarVentasAbiertas } from '../../services/modules/ventasService.js';
import { formatearCOP } from '../../utils/formato.js';
import { minutosDesde, textoDuracion } from '../../utils/tiempo.js';
import '../../styles/mesas.css';

const INTERVALO_ACTUALIZACION_MS = 10000;
const ESTADOS = {
  libre: 'Libre',
  ocupada: 'Ocupada',
  pendiente_pago: 'Pendiente de pago',
};

export default function Mesas() {
  const { esAdmin } = useAuth();
  const navegar = useNavigate();

  const [mesas, setMesas] = useState([]);
  const [ventas, setVentas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [reloj, setReloj] = useState(Date.now());

  const [mesaPorAbrir, setMesaPorAbrir] = useState(null);
  const [mesaPorEliminar, setMesaPorEliminar] = useState(null);
  const [nuevaAbierta, setNuevaAbierta] = useState(false);
  const [numeroNueva, setNumeroNueva] = useState('');
  const [procesando, setProcesando] = useState(false);

  // Bloque: carga mesas y ventas abiertas (para totales y tiempos) en paralelo
  const cargar = useCallback(async () => {
    try {
      const [listaMesas, listaVentas] = await Promise.all([listarMesas(), listarVentasAbiertas()]);
      setMesas([...listaMesas].sort((a, b) => a.numero.localeCompare(b.numero, 'es', { numeric: true })));
      setVentas(listaVentas);
      setError('');
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setCargando(false);
    }
  }, []);

  // Bloque: actualización automática cada 10 s, solo si la pestaña está visible
  useEffect(() => {
    cargar();
    const temporizador = setInterval(() => {
      if (document.visibilityState === 'visible') {
        cargar();
        setReloj(Date.now());
      }
    }, INTERVALO_ACTUALIZACION_MS);
    return () => clearInterval(temporizador);
  }, [cargar]);

  const ventaPorId = useMemo(() => Object.fromEntries(ventas.map((v) => [v.id, v])), [ventas]);
  const conteo = useMemo(
    () => ({
      libre: mesas.filter((m) => m.estado === 'libre').length,
      ocupada: mesas.filter((m) => m.estado === 'ocupada').length,
      pendiente_pago: mesas.filter((m) => m.estado === 'pendiente_pago').length,
    }),
    [mesas]
  );

  // Bloque: tocar una mesa. Libre: pide confirmar y abre cuenta; con cuenta: va al POS.
  function alTocarMesa(mesa) {
    if (mesa.estado === 'libre') {
      setMesaPorAbrir(mesa);
      return;
    }
    if (mesa.venta_abierta_id) navegar(`/pos?venta=${mesa.venta_abierta_id}`);
    else toast.warning(`La mesa ${mesa.numero} figura como "${ESTADOS[mesa.estado]}" pero no tiene una cuenta abierta.`);
  }

  async function abrirMesa() {
    setProcesando(true);
    try {
      const venta = await abrirVenta(mesaPorAbrir.id);
      navegar(`/pos?venta=${venta.id}`);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
      cargar();
    } finally {
      setProcesando(false);
      setMesaPorAbrir(null);
    }
  }

  async function agregarMesa(evento) {
    evento.preventDefault();
    const numero = numeroNueva.trim();
    if (!numero) {
      toast.error('Escribe el número o nombre de la mesa.');
      return;
    }
    setProcesando(true);
    try {
      await crearMesa(numero);
      toast.success(`Mesa ${numero} creada.`);
      setNuevaAbierta(false);
      setNumeroNueva('');
      cargar();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
    }
  }

  async function quitarMesa() {
    setProcesando(true);
    try {
      await eliminarMesa(mesaPorEliminar.id);
      toast.success(`Mesa ${mesaPorEliminar.numero} eliminada.`);
      cargar();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
      setMesaPorEliminar(null);
    }
  }

  return (
    <div className="mesas">
      {/* Resumen por estado y acciones */}
      <div className="mesas-barra">
        <div className="mesas-leyenda" aria-label="Resumen de mesas">
          <span className="etiqueta verde">{conteo.libre} libres</span>
          <span className="etiqueta ambar">{conteo.ocupada} ocupadas</span>
          <span className="etiqueta rojo">{conteo.pendiente_pago} pendientes de pago</span>
        </div>
        <div className="mesas-acciones">
          <button type="button" className="boton boton-secundario boton-compacto" onClick={cargar} aria-label="Actualizar mesas">
            <RefreshCw size={18} aria-hidden="true" /> <span className="solo-escritorio">Actualizar</span>
          </button>
          {esAdmin && (
            <button type="button" className="boton boton-primario boton-compacto" onClick={() => setNuevaAbierta(true)}>
              <Plus size={18} aria-hidden="true" /> Nueva mesa
            </button>
          )}
        </div>
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="mesas-rejilla">
          {Array.from({ length: 8 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 150 }} />)}
        </div>
      ) : mesas.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Armchair size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>Aún no hay mesas</h2>
          <p className="texto-suave">
            {esAdmin ? 'Crea la primera mesa con el botón "Nueva mesa".' : 'Pídele al administrador que cree las mesas.'}
          </p>
        </section>
      ) : (
        <div className="mesas-rejilla">
          <AnimatePresence>
            {mesas.map((mesa) => {
              const venta = ventaPorId[mesa.venta_abierta_id];
              const minutos = venta ? minutosDesde(venta.fecha_apertura) : null;
              return (
                <motion.div
                  key={mesa.id}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="mesa-envoltura"
                  data-reloj={reloj}
                >
                  <button
                    type="button"
                    className={`mesa ${mesa.estado}`}
                    onClick={() => alTocarMesa(mesa)}
                    aria-label={`Mesa ${mesa.numero}, ${ESTADOS[mesa.estado]}`}
                  >
                    <span className="mesa-numero">{mesa.numero}</span>
                    <span className="mesa-estado">{ESTADOS[mesa.estado]}</span>
                    {venta ? (
                      <>
                        <strong className="mesa-total">{formatearCOP(venta.total)}</strong>
                        <span className="mesa-tiempo">
                          <Clock size={13} aria-hidden="true" /> {textoDuracion(minutos)}
                        </span>
                      </>
                    ) : (
                      <span className="mesa-tiempo">{mesa.estado === 'libre' ? 'Toca para abrir' : 'Sin cuenta'}</span>
                    )}
                  </button>
                  {esAdmin && mesa.estado === 'libre' && (
                    <button type="button" className="mesa-eliminar" onClick={() => setMesaPorEliminar(mesa)} aria-label={`Eliminar mesa ${mesa.numero}`}>
                      <Trash2 size={15} />
                    </button>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      {/* Ventanas */}
      <Confirmar
        abierto={Boolean(mesaPorAbrir)}
        titulo="Abrir mesa"
        mensaje={`¿Abrir una cuenta nueva en la mesa ${mesaPorAbrir?.numero ?? ''}?`}
        textoConfirmar="Abrir mesa"
        cargando={procesando}
        onConfirmar={abrirMesa}
        onCancelar={() => setMesaPorAbrir(null)}
      />
      <Confirmar
        abierto={Boolean(mesaPorEliminar)}
        titulo="Eliminar mesa"
        mensaje={`¿Eliminar la mesa ${mesaPorEliminar?.numero ?? ''}? Esta acción no se puede deshacer.`}
        textoConfirmar="Eliminar"
        peligro
        cargando={procesando}
        onConfirmar={quitarMesa}
        onCancelar={() => setMesaPorEliminar(null)}
      />
      <Modal abierto={nuevaAbierta} onCerrar={() => setNuevaAbierta(false)} titulo="Nueva mesa" ancho={400} bloqueado={procesando}>
        <form onSubmit={agregarMesa} noValidate>
          <label className="campo">
            <span>Número o nombre</span>
            <div className="campo-caja">
              <input type="text" value={numeroNueva} onChange={(e) => setNumeroNueva(e.target.value)} maxLength={20} autoFocus placeholder="Ej. 12 o Terraza 1" />
            </div>
          </label>
          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={() => setNuevaAbierta(false)} disabled={procesando}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={procesando}>
              {procesando && <Loader2 size={18} className="girar" aria-hidden="true" />} Crear mesa
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}