// frontend/src/components/compras/FormularioCompra.jsx
// Ventana para registrar una compra a un proveedor: se elige el proveedor, se
// agregan productos (buscador o lector USB), se ingresan cantidades y costos, y
// se confirma antes de guardar. Una compra suma existencias y actualiza el
// costo de cada producto, y no se puede deshacer desde la interfaz.

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../common/Confirmar.jsx';
import Modal from '../common/Modal.jsx';
import BuscadorProducto from '../forms/BuscadorProducto.jsx';
import useLectorCodigoBarras from '../../hooks/useLectorCodigoBarras.js';
import { mensajeDeError } from '../../services/api.js';
import { registrarEscaneo } from '../../services/modules/catalogoService.js';
import { registrarCompra } from '../../services/modules/comprasService.js';
import { formatearCOP, formatearNumero } from '../../utils/formato.js';
import { aEntero, formatearMiles } from '../../utils/pos.js';

const CANTIDAD_MAXIMA = 100000;

export default function FormularioCompra({ abierto, proveedores, productos, onCerrar, onRegistrada }) {
  const [proveedorId, setProveedorId] = useState('');
  const [lineas, setLineas] = useState([]); // [{ producto, cantidad, costo }]
  const [error, setError] = useState('');
  const [confirmando, setConfirmando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  // Bloque: reinicia el formulario cada vez que se abre
  useEffect(() => {
    if (!abierto) return;
    setProveedorId('');
    setLineas([]);
    setError('');
    setConfirmando(false);
    setGuardando(false);
  }, [abierto]);

  // Bloque: agrega un producto; si ya estaba, suma una unidad. El costo parte del último registrado.
  function agregarProducto(producto) {
    setError('');
    setLineas((previo) => {
      if (previo.some((l) => l.producto.id === producto.id)) {
        return previo.map((l) =>
          l.producto.id === producto.id ? { ...l, cantidad: String((Number(l.cantidad) || 0) + 1) } : l
        );
      }
      const costoInicial = producto.precio_compra ? String(Math.round(producto.precio_compra)) : '';
      return [...previo, { producto, cantidad: '1', costo: costoInicial }];
    });
  }

  // Bloque: lector USB; el código debe corresponder a un producto activo del catálogo
  useLectorCodigoBarras((codigo) => {
    const producto = productos.find((p) => p.codigo_barras && p.codigo_barras.toLowerCase() === codigo.toLowerCase());
    registrarEscaneo(codigo, Boolean(producto), 'compras');
    if (!producto) {
      toast.error(`El código ${codigo} no existe en el inventario.`);
      return;
    }
    agregarProducto(producto);
    toast.success(`${producto.nombre} agregado`, { duration: 1500 });
  }, abierto && !confirmando);

  const cambiar = (idProducto, campo, valor) =>
    setLineas((previo) => previo.map((l) => (l.producto.id === idProducto ? { ...l, [campo]: valor } : l)));
  const quitar = (idProducto) => setLineas((previo) => previo.filter((l) => l.producto.id !== idProducto));

  // Bloque: totales calculados con los valores válidos de cada línea
  const totales = useMemo(() => {
    let dinero = 0;
    let unidades = 0;
    lineas.forEach((l) => {
      const cantidad = Number.parseInt(l.cantidad, 10) || 0;
      dinero += cantidad * aEntero(l.costo);
      unidades += cantidad;
    });
    return { dinero, unidades };
  }, [lineas]);

  // Bloque: valida y, si todo está bien, pide la confirmación final
  function revisar(evento) {
    evento.preventDefault();
    if (!proveedorId) return setError('Selecciona el proveedor.');
    if (lineas.length === 0) return setError('Agrega al menos un producto.');
    for (const l of lineas) {
      const cantidad = Number(l.cantidad);
      if (!Number.isInteger(cantidad) || cantidad < 1 || cantidad > CANTIDAD_MAXIMA) {
        return setError(`La cantidad de "${l.producto.nombre}" debe ser un entero entre 1 y ${CANTIDAD_MAXIMA.toLocaleString('es-CO')}.`);
      }
      if (aEntero(l.costo) <= 0) return setError(`Ingresa el costo unitario de "${l.producto.nombre}".`);
    }
    setError('');
    setConfirmando(true);
  }

  async function guardar() {
    setGuardando(true);
    try {
      const compra = await registrarCompra(
        Number(proveedorId),
        lineas.map((l) => ({
          producto_id: l.producto.id,
          cantidad: Number(l.cantidad),
          costo_unitario: aEntero(l.costo),
        }))
      );
      toast.success(`Compra #${compra.id} registrada. El inventario se actualizó.`);
      setConfirmando(false);
      onRegistrada();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
      setConfirmando(false);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <Modal abierto={abierto} onCerrar={onCerrar} titulo="Registrar compra" ancho={860} bloqueado={guardando || confirmando}>
        <form onSubmit={revisar} noValidate>
          <label className="campo">
            <span>Proveedor</span>
            <div className="campo-caja">
              <select
                value={proveedorId}
                onChange={(e) => {
                  setProveedorId(e.target.value);
                  e.target.blur(); // Libera el foco para que el lector USB siga funcionando
                }}
              >
                <option value="">Selecciona un proveedor…</option>
                {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
          </label>

          <div className="campo">
            <span className="etiqueta-campo">Productos</span>
            <BuscadorProducto productos={productos} onElegir={agregarProducto} />
            <small className="campo-ayuda">También puedes escanear el código con el lector USB.</small>
          </div>

          {lineas.length === 0 ? (
            <p className="texto-suave estado-vacio-simple">Aún no has agregado productos.</p>
          ) : (
            <ul className="compra-lineas">
              {lineas.map((l) => {
                const cantidad = Number.parseInt(l.cantidad, 10) || 0;
                const costo = aEntero(l.costo);
                const costoAlto = costo > l.producto.precio_venta;
                return (
                  <li key={l.producto.id} className="compra-linea">
                    <div className="compra-linea-nombre">
                      <strong>{l.producto.nombre}</strong>
                      <span className="texto-suave">
                        Existencias: {formatearNumero(l.producto.stock_actual)} · Venta: {formatearCOP(l.producto.precio_venta)}
                      </span>
                      {costoAlto && (
                        <span className="etiqueta rojo">
                          <AlertTriangle size={12} aria-hidden="true" /> Costo mayor al precio de venta
                        </span>
                      )}
                    </div>
                    <label className="compra-campo">
                      <span>Cantidad</span>
                      <input
                        type="number"
                        inputMode="numeric"
                        min="1"
                        max={CANTIDAD_MAXIMA}
                        step="1"
                        value={l.cantidad}
                        onChange={(e) => cambiar(l.producto.id, 'cantidad', e.target.value)}
                      />
                    </label>
                    <label className="compra-campo">
                      <span>Costo unitario</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        placeholder="$ 0"
                        value={formatearMiles(costo)}
                        onChange={(e) => cambiar(l.producto.id, 'costo', String(aEntero(e.target.value) || ''))}
                      />
                    </label>
                    <strong className="compra-subtotal">{formatearCOP(cantidad * costo)}</strong>
                    <button type="button" className="boton-icono" onClick={() => quitar(l.producto.id)} aria-label={`Quitar ${l.producto.nombre}`}>
                      <Trash2 size={18} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="compra-total">
            <span className="texto-suave">{formatearNumero(totales.unidades)} unidad(es)</span>
            <span>Total de la compra</span>
            <strong>{formatearCOP(totales.dinero)}</strong>
          </div>

          {error && <p className="mensaje-error" role="alert">{error}</p>}

          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={guardando}>Revisar y registrar</button>
          </div>
        </form>
      </Modal>

      <Confirmar
        abierto={confirmando}
        titulo="Confirmar compra"
        mensaje={`Se registrará una compra por ${formatearCOP(totales.dinero)} y se sumarán ${formatearNumero(totales.unidades)} unidad(es) al inventario. Esta acción no se puede deshacer desde el sistema.`}
        textoConfirmar={guardando ? 'Registrando…' : 'Registrar compra'}
        cargando={guardando}
        onConfirmar={guardar}
        onCancelar={() => setConfirmando(false)}
      />
      {guardando && <Loader2 className="girar oculto-visual" aria-label="Registrando compra" />}
    </>
  );
}