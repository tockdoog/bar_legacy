// frontend/src/components/configuracion/PanelFinanzas.jsx
// Sección "Impuestos y margen": configuración global del negocio (tipo de
// impuesto, porcentaje, margen de utilidad deseado y margen mínimo saludable).
// Requiere el permiso "finanzas_gestionar". Los cambios aplican a ventas
// nuevas: las facturas ya emitidas conservan el impuesto con que se vendieron.

import { useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import Campo from '../forms/Campo.jsx';
import { mensajeDeError } from '../../services/api.js';
import {
  actualizarConfiguracionFinanciera,
  obtenerConfiguracionFinanciera,
} from '../../services/modules/configuracionService.js';
import { listarTiposImpuesto } from '../../services/modules/productosService.js';

// Bloque: tipos de respaldo (iguales a los del backend) por si la consulta falla
const TIPOS_BASE = [
  { tipo: 'sin_impuesto', etiqueta: 'Sin impuesto', porcentaje_referencia: 0 },
  { tipo: 'iva', etiqueta: 'IVA (Colombia)', porcentaje_referencia: 19 },
  { tipo: 'inc', etiqueta: 'INC - Impuesto Nacional al Consumo (Colombia)', porcentaje_referencia: 8 },
  { tipo: 'personalizado', etiqueta: 'Impuesto personalizado', porcentaje_referencia: 0 },
];

// Bloque: convierte la configuración del backend en valores de formulario (texto)
const aValores = (c) => ({
  tipo: c.tipo_impuesto,
  porcentaje: String(c.porcentaje_impuesto),
  nombre: c.nombre_impuesto_personalizado ?? '',
  margen: String(c.margen_utilidad_deseado),
  minimo: String(c.margen_minimo_saludable),
});

export default function PanelFinanzas() {
  const [valores, setValores] = useState(null);
  const [tipos, setTipos] = useState(TIPOS_BASE);
  const [errores, setErrores] = useState({});
  const [errorCarga, setErrorCarga] = useState('');
  const [guardando, setGuardando] = useState(false);

  // Bloque: carga la configuración actual y los tipos de impuesto disponibles
  useEffect(() => {
    Promise.all([obtenerConfiguracionFinanciera(), listarTiposImpuesto().catch(() => TIPOS_BASE)])
      .then(([configuracion, listaTipos]) => {
        setValores(aValores(configuracion));
        setTipos(listaTipos);
      })
      .catch((fallo) => setErrorCarga(mensajeDeError(fallo)));
  }, []);

  const poner = (campo) => (evento) => setValores((previo) => ({ ...previo, [campo]: evento.target.value }));

  // Bloque: al cambiar el tipo se sugiere su porcentaje de referencia (editable)
  function cambiarTipo(evento) {
    const tipo = evento.target.value;
    const referencia = tipos.find((t) => t.tipo === tipo)?.porcentaje_referencia ?? 0;
    setValores((previo) => ({
      ...previo,
      tipo,
      porcentaje: tipo === 'personalizado' ? previo.porcentaje : String(referencia),
    }));
  }

  async function guardar(evento) {
    evento.preventDefault();
    const e = {};
    const porcentaje = Number(valores.porcentaje);
    const margen = Number(valores.margen);
    const minimo = Number(valores.minimo);
    if (valores.porcentaje === '' || Number.isNaN(porcentaje) || porcentaje < 0 || porcentaje > 100) e.porcentaje = 'Debe estar entre 0 y 100.';
    if (valores.tipo === 'personalizado' && !valores.nombre.trim()) e.nombre = 'Indica el nombre del impuesto.';
    if (valores.margen === '' || Number.isNaN(margen) || margen <= 0 || margen > 95) e.margen = 'Debe ser mayor a 0 y hasta 95.';
    if (valores.minimo === '' || Number.isNaN(minimo) || minimo < 0 || minimo > 95) e.minimo = 'Debe estar entre 0 y 95.';
    setErrores(e);
    if (Object.keys(e).length > 0) return;

    setGuardando(true);
    try {
      const guardada = await actualizarConfiguracionFinanciera({
        tipo_impuesto: valores.tipo,
        porcentaje_impuesto: porcentaje,
        nombre_impuesto_personalizado: valores.tipo === 'personalizado' ? valores.nombre.trim() : null,
        margen_utilidad_deseado: margen,
        margen_minimo_saludable: minimo,
      });
      setValores(aValores(guardada));
      toast.success('Configuración financiera guardada.');
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  if (errorCarga) return <p className="mensaje-error" role="alert">{errorCarga}</p>;
  if (!valores) return <div className="tarjeta"><div className="esqueleto" style={{ height: 220 }} /></div>;

  const minimoMayor = Number(valores.minimo) > Number(valores.margen);

  return (
    <section className="tarjeta" aria-labelledby="titulo-finanzas">
      <h3 id="titulo-finanzas">Impuestos y margen del negocio</h3>
      <p className="texto-suave">
        Se aplica a todos los productos que no tengan una configuración propia. Los cambios valen para ventas nuevas; las facturas ya emitidas no se modifican.
      </p>
      <form onSubmit={guardar} noValidate>
        <div className="formulario-rejilla">
          <Campo etiqueta="Tipo de impuesto">
            <select value={valores.tipo} onChange={cambiarTipo}>
              {tipos.map((t) => <option key={t.tipo} value={t.tipo}>{t.etiqueta}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Porcentaje de impuesto (%)" error={errores.porcentaje} ayuda="La tarifa vigente puede cambiar: ajústala si hace falta.">
            <input type="number" min="0" max="100" step="0.01" value={valores.porcentaje} onChange={poner('porcentaje')} />
          </Campo>
          {valores.tipo === 'personalizado' && (
            <Campo etiqueta="Nombre del impuesto" error={errores.nombre} className="ocupa-todo">
              <input type="text" value={valores.nombre} onChange={poner('nombre')} maxLength={80} />
            </Campo>
          )}
          <Campo etiqueta="Margen de utilidad deseado (%)" error={errores.margen} ayuda="Sobre el precio de venta. Base de los precios recomendados.">
            <input type="number" min="0" max="95" step="0.01" value={valores.margen} onChange={poner('margen')} />
          </Campo>
          <Campo etiqueta="Margen mínimo saludable (%)" error={errores.minimo} ayuda="Por debajo de este margen se avisa de bajo margen.">
            <input type="number" min="0" max="95" step="0.01" value={valores.minimo} onChange={poner('minimo')} />
          </Campo>
        </div>
        {minimoMayor && (
          <p className="aviso-form"><AlertTriangle size={16} aria-hidden="true" /> El margen mínimo es mayor al deseado: casi todos los productos aparecerán con bajo margen.</p>
        )}
        <div className="modal-acciones">
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />} Guardar configuración
          </button>
        </div>
      </form>
    </section>
  );
}