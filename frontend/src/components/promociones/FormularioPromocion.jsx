// frontend/src/components/promociones/FormularioPromocion.jsx
// Ventana para crear o editar una promoción (combo). Se eligen los productos y
// sus cantidades, y se muestra al instante el valor normal, el ahorro del
// cliente, el costo y el margen del negocio. Avisa si no hay ahorro o si se
// vendería por debajo del costo. Solo la usa el administrador.

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import Campo from '../forms/Campo.jsx';
import BuscadorProducto from '../forms/BuscadorProducto.jsx';
import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import { actualizarPromocion, crearPromocion } from '../../services/modules/promocionesService.js';
import { formatearCOP } from '../../utils/formato.js';
import { aEntero, formatearMiles } from '../../utils/pos.js';

const CANTIDAD_MAXIMA = 1000;

export default function FormularioPromocion({ abierto, promocion, productos, onCerrar, onGuardado }) {
  const esEdicion = Boolean(promocion);
  const [nombre, setNombre] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [precio, setPrecio] = useState('');
  const [items, setItems] = useState([]); // [{ producto_id, nombre, cantidad }]
  const [errores, setErrores] = useState({});
  const [guardando, setGuardando] = useState(false);

  // Bloque: reinicia el formulario al abrir, partiendo de la promoción si se edita
  useEffect(() => {
    if (!abierto) return;
    setNombre(promocion?.nombre ?? '');
    setDescripcion(promocion?.descripcion ?? '');
    setPrecio(promocion ? String(Math.round(promocion.precio_promocional)) : '');
    setItems(
      (promocion?.componentes ?? []).map((c) => ({
        producto_id: c.producto_id,
        nombre: c.nombre_producto,
        cantidad: String(c.cantidad),
      }))
    );
    setErrores({});
    setGuardando(false);
  }, [abierto, promocion]);

  const productoPorId = useMemo(() => Object.fromEntries(productos.map((p) => [p.id, p])), [productos]);

  // Bloque: agrega un producto; si ya estaba, suma una unidad (el backend no admite repetidos)
  function agregar(producto) {
    setErrores((previo) => ({ ...previo, items: undefined }));
    setItems((previo) => {
      if (previo.some((i) => i.producto_id === producto.id)) {
        return previo.map((i) =>
          i.producto_id === producto.id ? { ...i, cantidad: String((Number(i.cantidad) || 0) + 1) } : i
        );
      }
      return [...previo, { producto_id: producto.id, nombre: producto.nombre, cantidad: '1' }];
    });
  }

  // Bloque: vista previa financiera con los precios actuales de los productos
  const calculo = useMemo(() => {
    let valorNormal = 0;
    let costo = 0;
    let costoDisponible = true;
    items.forEach((i) => {
      const cantidad = Number.parseInt(i.cantidad, 10) || 0;
      const producto = productoPorId[i.producto_id];
      if (!producto) return;
      valorNormal += cantidad * producto.precio_venta;
      if (producto.precio_compra === null || producto.precio_compra === undefined) costoDisponible = false;
      else costo += cantidad * producto.precio_compra;
    });
    const precioPromo = aEntero(precio);
    return {
      valorNormal,
      ahorro: valorNormal - precioPromo,
      costo: costoDisponible ? costo : null,
      ganancia: costoDisponible ? precioPromo - costo : null,
      margen: costoDisponible && precioPromo > 0 ? ((precioPromo - costo) / precioPromo) * 100 : null,
      precioPromo,
    };
  }, [items, precio, productoPorId]);

  async function guardar(evento) {
    evento.preventDefault();
    const encontrados = {};
    if (nombre.trim().length < 3) encontrados.nombre = 'Escribe al menos 3 caracteres.';
    if (calculo.precioPromo <= 0) encontrados.precio = 'Ingresa el precio promocional.';
    if (items.length === 0) encontrados.items = 'Agrega al menos un producto.';
    else if (items.some((i) => !Number.isInteger(Number(i.cantidad)) || Number(i.cantidad) < 1 || Number(i.cantidad) > CANTIDAD_MAXIMA)) {
      encontrados.items = `Cada cantidad debe ser un entero entre 1 y ${CANTIDAD_MAXIMA}.`;
    }
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) return;

    const carga = {
      nombre: nombre.trim(),
      descripcion: descripcion.trim() || null,
      precio_promocional: calculo.precioPromo,
      items: items.map((i) => ({ producto_id: i.producto_id, cantidad: Number(i.cantidad) })),
    };

    setGuardando(true);
    try {
      if (esEdicion) await actualizarPromocion(promocion.id, carga);
      else await crearPromocion(carga);
      toast.success(esEdicion ? 'Promoción actualizada.' : 'Promoción creada.');
      onGuardado();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  const sinAhorro = items.length > 0 && calculo.valorNormal > 0 && calculo.precioPromo >= calculo.valorNormal;
  const enPerdida = calculo.ganancia !== null && calculo.precioPromo > 0 && calculo.ganancia < 0;

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={esEdicion ? 'Editar promoción' : 'Nueva promoción'} ancho={720} bloqueado={guardando}>
      <form onSubmit={guardar} noValidate>
        <Campo etiqueta="Nombre" error={errores.nombre}>
          <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={120} autoFocus placeholder="Ej. Combo de la casa" />
        </Campo>
        <Campo etiqueta="Descripción (opcional)">
          <input type="text" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={255} />
        </Campo>
        <Campo etiqueta="Precio promocional (COP)" error={errores.precio}>
          <span aria-hidden="true">$</span>
          <input type="text" inputMode="numeric" value={formatearMiles(calculo.precioPromo)} onChange={(e) => setPrecio(String(aEntero(e.target.value) || ''))} />
        </Campo>

        <div className="campo">
          <span className="etiqueta-campo">Productos del combo</span>
          <BuscadorProducto productos={productos} onElegir={agregar} deshabilitado={guardando} />
          {errores.items && <small className="campo-error" role="alert">{errores.items}</small>}
        </div>

        {items.length > 0 && (
          <ul className="compra-lineas promo-items">
            {items.map((i) => (
              <li key={i.producto_id} className="promo-item">
                <div className="compra-linea-nombre">
                  <strong>{i.nombre}</strong>
                  <span className="texto-suave">
                    {productoPorId[i.producto_id]
                      ? `Precio normal: ${formatearCOP(productoPorId[i.producto_id].precio_venta)}`
                      : 'Producto inactivo: no se cuenta en el cálculo'}
                  </span>
                </div>
                <label className="compra-campo">
                  <span>Cantidad</span>
                  <input
                    type="number"
                    inputMode="numeric"
                    min="1"
                    max={CANTIDAD_MAXIMA}
                    step="1"
                    value={i.cantidad}
                    onChange={(e) =>
                      setItems((previo) => previo.map((x) => (x.producto_id === i.producto_id ? { ...x, cantidad: e.target.value } : x)))
                    }
                  />
                </label>
                <button
                  type="button"
                  className="boton-icono"
                  onClick={() => setItems((previo) => previo.filter((x) => x.producto_id !== i.producto_id))}
                  aria-label={`Quitar ${i.nombre}`}
                >
                  <Trash2 size={18} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Vista previa financiera */}
        {items.length > 0 && (
          <dl className="vista-previa-promo" aria-live="polite">
            <div><dt>Valor normal</dt><dd>{formatearCOP(calculo.valorNormal)}</dd></div>
            <div><dt>Ahorro del cliente</dt><dd>{formatearCOP(Math.max(calculo.ahorro, 0))}</dd></div>
            {calculo.costo !== null && (
              <>
                <div><dt>Costo</dt><dd>{formatearCOP(calculo.costo)}</dd></div>
                <div>
                  <dt>Ganancia</dt>
                  <dd className={calculo.ganancia < 0 ? 'texto-rojo' : 'texto-verde'}>
                    {formatearCOP(calculo.ganancia)}
                    {calculo.margen !== null && ` (${calculo.margen.toFixed(1).replace('.', ',')} %)`}
                  </dd>
                </div>
              </>
            )}
          </dl>
        )}
        {sinAhorro && (
          <p className="aviso-form"><AlertTriangle size={16} aria-hidden="true" /> El precio promocional no es menor al valor normal: el cliente no ahorra.</p>
        )}
        {enPerdida && (
          <p className="aviso-form critico"><AlertTriangle size={16} aria-hidden="true" /> Con este precio la promoción se vende por debajo del costo.</p>
        )}

        <div className="modal-acciones">
          <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />}
            {esEdicion ? 'Guardar cambios' : 'Crear promoción'}
          </button>
        </div>
      </form>
    </Modal>
  );
}