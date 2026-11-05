// frontend/src/components/productos/FormularioProducto.jsx
// Ventana para crear o editar un producto. Valida en el cliente las mismas
// reglas del backend, guarda el producto y luego sube o quita la imagen. La
// sección de impuesto y margen propio solo aparece con el permiso
// "finanzas_gestionar". Admite lector USB (el campo recibe el código) y cámara.

import { useEffect, useState } from 'react';
import { Camera, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import Campo from '../forms/Campo.jsx';
import Modal from '../common/Modal.jsx';
import CampoImagen from './CampoImagen.jsx';
import { mensajeDeError } from '../../services/api.js';
import {
  actualizarProducto,
  crearProducto,
  listarTiposImpuesto,
  quitarImagenProducto,
  subirImagenProducto,
} from '../../services/modules/productosService.js';
import { aEntero, formatearMiles } from '../../utils/pos.js';

const REGEX_CODIGO = /^[A-Za-z0-9-]{4,64}$/;

// Bloque: tipos de impuesto de respaldo (iguales a los del backend) por si la consulta falla
const TIPOS_BASE = [
  { tipo: 'sin_impuesto', etiqueta: 'Sin impuesto', porcentaje_referencia: 0 },
  { tipo: 'iva', etiqueta: 'IVA (Colombia)', porcentaje_referencia: 19 },
  { tipo: 'inc', etiqueta: 'INC - Impuesto Nacional al Consumo (Colombia)', porcentaje_referencia: 8 },
  { tipo: 'personalizado', etiqueta: 'Impuesto personalizado', porcentaje_referencia: 0 },
];

// Bloque: valores iniciales del formulario (de un producto existente o vacíos)
function valoresIniciales(producto) {
  return {
    nombre: producto?.nombre ?? '',
    codigo_barras: producto?.codigo_barras ?? '',
    categoria_id: producto?.categoria_id ? String(producto.categoria_id) : '',
    presentacion: producto?.presentacion ?? 'unidad',
    precio_compra: String(Math.round(producto?.precio_compra ?? 0) || ''),
    precio_venta: String(Math.round(producto?.precio_venta ?? 0) || ''),
    stock_actual: String(producto?.stock_actual ?? 0),
    stock_minimo: String(producto?.stock_minimo ?? 0),
    usar_global: producto?.usar_configuracion_global ?? true,
    tipo_impuesto: producto?.tipo_impuesto_propio ?? 'sin_impuesto',
    porcentaje: String(producto?.porcentaje_impuesto_propio ?? 0),
    nombre_personalizado: producto?.nombre_impuesto_propio_personalizado ?? '',
    margen: producto?.margen_utilidad_propio ? String(producto.margen_utilidad_propio) : '',
  };
}

// Bloque: validación; devuelve un objeto { campo: mensaje } (vacío si todo es correcto)
function validar(v, puedeFinanzas) {
  const e = {};
  if (v.nombre.trim().length < 2) e.nombre = 'Escribe al menos 2 caracteres.';
  const codigo = v.codigo_barras.trim();
  if (codigo && !REGEX_CODIGO.test(codigo)) e.codigo_barras = 'Solo letras, números y guiones (4 a 64 caracteres).';
  if (!v.presentacion.trim()) e.presentacion = 'Indica la presentación.';

  const compra = aEntero(v.precio_compra);
  const venta = aEntero(v.precio_venta);
  if (venta <= 0) e.precio_venta = 'Ingresa el precio de venta.';
  else if (venta < compra) e.precio_venta = 'No puede ser menor al precio de compra.';

  if (!/^\d+$/.test(v.stock_actual)) e.stock_actual = 'Ingresa un número entero.';
  if (!/^\d+$/.test(v.stock_minimo)) e.stock_minimo = 'Ingresa un número entero.';

  if (puedeFinanzas && !v.usar_global) {
    if (v.tipo_impuesto === 'personalizado' && !v.nombre_personalizado.trim()) {
      e.nombre_personalizado = 'Indica el nombre del impuesto.';
    }
    const porcentaje = Number(v.porcentaje);
    if (v.porcentaje === '' || Number.isNaN(porcentaje) || porcentaje < 0 || porcentaje > 100) {
      e.porcentaje = 'Debe estar entre 0 y 100.';
    }
    if (v.margen !== '') {
      const margen = Number(v.margen);
      if (Number.isNaN(margen) || margen <= 0 || margen > 95) e.margen = 'Debe ser mayor a 0 y hasta 95.';
    }
  }
  return e;
}

export default function FormularioProducto({
  abierto,
  producto,
  categorias,
  presentaciones,
  puedeFinanzas,
  codigoEscaneado,
  onEscanear,
  onCerrar,
  onGuardado,
}) {
  const esEdicion = Boolean(producto);
  const [valores, setValores] = useState(valoresIniciales(null));
  const [errores, setErrores] = useState({});
  const [archivo, setArchivo] = useState(null);
  const [imagenQuitada, setImagenQuitada] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [tipos, setTipos] = useState(TIPOS_BASE);

  // Bloque: reinicia el formulario cada vez que se abre
  useEffect(() => {
    if (!abierto) return;
    setValores(valoresIniciales(producto));
    setErrores({});
    setArchivo(null);
    setImagenQuitada(false);
    setGuardando(false);
  }, [abierto, producto]);

  // Bloque: trae los tipos de impuesto reales del backend (solo con permiso de finanzas)
  useEffect(() => {
    if (!abierto || !puedeFinanzas) return;
    listarTiposImpuesto().then(setTipos).catch(() => setTipos(TIPOS_BASE));
  }, [abierto, puedeFinanzas]);

  // Bloque: un código leído con la cámara llena el campo del código de barras
  useEffect(() => {
    if (abierto && codigoEscaneado?.valor) {
      setValores((previo) => ({ ...previo, codigo_barras: codigoEscaneado.valor }));
    }
  }, [codigoEscaneado, abierto]);

  const poner = (campo) => (evento) => setValores((previo) => ({ ...previo, [campo]: evento.target.value }));
  const ponerDinero = (campo) => (evento) =>
    setValores((previo) => ({ ...previo, [campo]: String(aEntero(evento.target.value) || '') }));

  // Bloque: al cambiar el tipo de impuesto se sugiere su porcentaje de referencia
  function cambiarTipo(evento) {
    const tipo = evento.target.value;
    const referencia = tipos.find((t) => t.tipo === tipo)?.porcentaje_referencia ?? 0;
    setValores((previo) => ({
      ...previo,
      tipo_impuesto: tipo,
      porcentaje: tipo === 'personalizado' ? previo.porcentaje : String(referencia),
    }));
  }

  // Bloque: valida, guarda el producto y después actualiza la imagen
  async function guardar(evento) {
    evento.preventDefault();
    const encontrados = validar(valores, puedeFinanzas);
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) {
      toast.error('Revisa los campos marcados.');
      return;
    }

    const carga = {
      nombre: valores.nombre.trim(),
      codigo_barras: valores.codigo_barras.trim() || null,
      categoria_id: valores.categoria_id ? Number(valores.categoria_id) : null,
      presentacion: valores.presentacion.trim(),
      precio_compra: aEntero(valores.precio_compra),
      precio_venta: aEntero(valores.precio_venta),
      stock_actual: Number(valores.stock_actual),
      stock_minimo: Number(valores.stock_minimo),
    };
    if (puedeFinanzas) {
      carga.usar_configuracion_global = valores.usar_global;
      if (!valores.usar_global) {
        carga.tipo_impuesto_propio = valores.tipo_impuesto;
        carga.porcentaje_impuesto_propio = Number(valores.porcentaje);
        carga.nombre_impuesto_propio_personalizado =
          valores.tipo_impuesto === 'personalizado' ? valores.nombre_personalizado.trim() : null;
        carga.margen_utilidad_propio = valores.margen !== '' ? Number(valores.margen) : null;
      }
    }

    setGuardando(true);
    try {
      const guardado = esEdicion
        ? await actualizarProducto(producto.id, carga)
        : await crearProducto(carga);

      // La imagen se maneja aparte: si falla, el producto ya quedó guardado
      try {
        if (archivo) await subirImagenProducto(guardado.id, archivo);
        else if (imagenQuitada && producto?.imagen_url) await quitarImagenProducto(guardado.id);
      } catch (fallo) {
        toast.warning(`Producto guardado, pero la imagen no se actualizó: ${mensajeDeError(fallo)}`);
      }

      toast.success(esEdicion ? 'Producto actualizado.' : 'Producto creado.');
      onGuardado();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={esEdicion ? 'Editar producto' : 'Nuevo producto'} ancho={700} bloqueado={guardando}>
      <form onSubmit={guardar} noValidate>
        <CampoImagen
          imagenActual={producto?.imagen_url}
          archivo={archivo}
          quitada={imagenQuitada}
          deshabilitado={guardando}
          onSeleccionar={(f) => {
            setArchivo(f);
            setImagenQuitada(false);
          }}
          onQuitar={() => {
            setArchivo(null);
            setImagenQuitada(true);
          }}
        />

        <div className="formulario-rejilla">
          <Campo etiqueta="Nombre" error={errores.nombre} className="ocupa-todo">
            <input type="text" value={valores.nombre} onChange={poner('nombre')} maxLength={120} autoFocus />
          </Campo>

          <Campo etiqueta="Código de barras (opcional)" error={errores.codigo_barras} ayuda="Escanéalo con el lector USB o la cámara.">
            <input
              type="text"
              value={valores.codigo_barras}
              onChange={poner('codigo_barras')}
              onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()}
              maxLength={64}
              autoComplete="off"
            />
            {onEscanear && (
              <button type="button" className="boton-icono" onClick={onEscanear} aria-label="Escanear código con la cámara">
                <Camera size={18} />
              </button>
            )}
          </Campo>

          <Campo etiqueta="Categoría">
            <select value={valores.categoria_id} onChange={poner('categoria_id')}>
              <option value="">Sin categoría</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </Campo>

          <Campo etiqueta="Presentación" error={errores.presentacion}>
            <input type="text" list="lista-presentaciones" value={valores.presentacion} onChange={poner('presentacion')} maxLength={60} />
            <datalist id="lista-presentaciones">
              {['unidad', 'paquete', 'caja', ...presentaciones.map((p) => p.nombre)]
                .filter((valor, indice, lista) => lista.indexOf(valor) === indice)
                .map((valor) => <option key={valor} value={valor} />)}
            </datalist>
          </Campo>

          <Campo etiqueta="Precio de compra (COP)">
            <span aria-hidden="true">$</span>
            <input type="text" inputMode="numeric" value={formatearMiles(aEntero(valores.precio_compra))} onChange={ponerDinero('precio_compra')} />
          </Campo>

          <Campo etiqueta="Precio de venta (COP)" error={errores.precio_venta}>
            <span aria-hidden="true">$</span>
            <input type="text" inputMode="numeric" value={formatearMiles(aEntero(valores.precio_venta))} onChange={ponerDinero('precio_venta')} />
          </Campo>

          <Campo etiqueta="Existencias" error={errores.stock_actual}>
            <input type="number" inputMode="numeric" min="0" step="1" value={valores.stock_actual} onChange={poner('stock_actual')} />
          </Campo>

          <Campo etiqueta="Stock mínimo" error={errores.stock_minimo} ayuda="Se avisa cuando las existencias lleguen a este número.">
            <input type="number" inputMode="numeric" min="0" step="1" value={valores.stock_minimo} onChange={poner('stock_minimo')} />
          </Campo>
        </div>

        {/* Impuesto y margen propios: solo para quien tiene el permiso de finanzas */}
        {puedeFinanzas && (
          <div className="seccion-form">
            <label className="casilla">
              <input
                type="checkbox"
                checked={valores.usar_global}
                onChange={(e) => setValores((previo) => ({ ...previo, usar_global: e.target.checked }))}
              />
              <span>Usar el impuesto y el margen configurados para todo el negocio</span>
            </label>

            {!valores.usar_global && (
              <div className="formulario-rejilla">
                <Campo etiqueta="Tipo de impuesto">
                  <select value={valores.tipo_impuesto} onChange={cambiarTipo}>
                    {tipos.map((t) => (
                      <option key={t.tipo} value={t.tipo}>{t.etiqueta}</option>
                    ))}
                  </select>
                </Campo>
                <Campo etiqueta="Porcentaje de impuesto (%)" error={errores.porcentaje}>
                  <input type="number" min="0" max="100" step="0.01" value={valores.porcentaje} onChange={poner('porcentaje')} />
                </Campo>
                {valores.tipo_impuesto === 'personalizado' && (
                  <Campo etiqueta="Nombre del impuesto" error={errores.nombre_personalizado}>
                    <input type="text" value={valores.nombre_personalizado} onChange={poner('nombre_personalizado')} maxLength={80} />
                  </Campo>
                )}
                <Campo etiqueta="Margen de utilidad propio (%)" error={errores.margen} ayuda="Opcional. Vacío usa el margen del negocio.">
                  <input type="number" min="0" max="95" step="0.01" value={valores.margen} onChange={poner('margen')} />
                </Campo>
              </div>
            )}
          </div>
        )}

        <div className="modal-acciones">
          <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />}
            {esEdicion ? 'Guardar cambios' : 'Crear producto'}
          </button>
        </div>
      </form>
    </Modal>
  );
}