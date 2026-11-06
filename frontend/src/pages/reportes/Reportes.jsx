// frontend/src/pages/reportes/Reportes.jsx
// Reportes: ocho tipos del backend con periodo (rápido o personalizado),
// indicadores del resumen, gráfica, tabla paginada y exportación a PDF y Excel.
// Requiere el permiso "reportes_ver". Las fechas son días de Colombia.

import { useEffect, useState } from 'react';
import { BarChart3, FileSpreadsheet, FileText, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import TarjetaEstadistica from '../../components/common/TarjetaEstadistica.jsx';
import GraficaReporte from '../../components/reportes/GraficaReporte.jsx';
import TablaReporte from '../../components/reportes/TablaReporte.jsx';
import { mensajeDeError } from '../../services/api.js';
import { descargarReporte, obtenerReporte } from '../../services/modules/reportesService.js';
import { formatearCOP, formatearNumero, hoyBogota } from '../../utils/formato.js';
import { PERIODOS, TIPOS_REPORTE, esResumenMonetario, rangoPeriodo } from '../../utils/reportes.js';
import '../../styles/catalogo.css';
import '../../styles/reportes.css';

export default function Reportes() {
  const [tipo, setTipo] = useState('ventas');
  const [periodo, setPeriodo] = useState('30d');
  const [desde, setDesde] = useState(() => rangoPeriodo('30d', hoyBogota()).desde);
  const [hasta, setHasta] = useState(() => hoyBogota());
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [descargando, setDescargando] = useState('');
  const [recarga, setRecarga] = useState(0);

  const meta = TIPOS_REPORTE.find((t) => t.id === tipo);
  const rangoInvalido = meta.usaFechas && desde > hasta;

  // Bloque: carga el reporte al cambiar tipo o fechas; ignora respuestas de consultas ya reemplazadas
  useEffect(() => {
    if (!desde || !hasta || rangoInvalido) return undefined;
    let vigente = true;
    setCargando(true);
    setError('');
    obtenerReporte(tipo, meta.usaFechas ? desde : undefined, meta.usaFechas ? hasta : undefined)
      .then((respuesta) => vigente && setDatos(respuesta))
      .catch((fallo) => {
        if (!vigente) return;
        setDatos(null);
        setError(mensajeDeError(fallo));
      })
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
  }, [tipo, desde, hasta, rangoInvalido, meta.usaFechas, recarga]);

  // Bloque: aplica un periodo rápido
  function elegirPeriodo(id) {
    const rango = rangoPeriodo(id, hoyBogota());
    setPeriodo(id);
    setDesde(rango.desde);
    setHasta(rango.hasta);
  }

  // Bloque: descarga el reporte en el formato pedido
  async function exportar(formato) {
    setDescargando(formato);
    try {
      await descargarReporte(tipo, formato, meta.usaFechas ? desde : undefined, meta.usaFechas ? hasta : undefined);
      toast.success(`Reporte exportado a ${formato === 'pdf' ? 'PDF' : 'Excel'}.`);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setDescargando('');
    }
  }

  const resumen = datos ? Object.entries(datos.resumen) : [];

  return (
    <div className="catalogo">
      {/* Selector de reporte */}
      <div className="pos-categorias" role="group" aria-label="Tipo de reporte">
        {TIPOS_REPORTE.map((t) => (
          <button key={t.id} type="button" className={`chip ${tipo === t.id ? 'activo' : ''}`} onClick={() => setTipo(t.id)}>
            {t.etiqueta}
          </button>
        ))}
      </div>
      <p className="texto-suave reporte-descripcion">{meta.descripcion}</p>

      {/* Periodo y acciones */}
      <div className="catalogo-barra">
        {meta.usaFechas && (
          <>
            <div className="selector-periodo" role="group" aria-label="Periodo rápido">
              {PERIODOS.map((p) => (
                <button key={p.id} type="button" className={periodo === p.id ? 'activo' : ''} onClick={() => elegirPeriodo(p.id)}>
                  {p.etiqueta}
                </button>
              ))}
            </div>
            <label className="filtro-fecha">
              <span className="texto-suave">Desde</span>
              <input type="date" className="filtro-select" value={desde} max={hasta} onChange={(e) => { setDesde(e.target.value); setPeriodo('personalizado'); }} />
            </label>
            <label className="filtro-fecha">
              <span className="texto-suave">Hasta</span>
              <input type="date" className="filtro-select" value={hasta} min={desde} max={hoyBogota()} onChange={(e) => { setHasta(e.target.value); setPeriodo('personalizado'); }} />
            </label>
          </>
        )}
        <span className="reporte-espacio" />
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => setRecarga((n) => n + 1)} aria-label="Actualizar reporte">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => exportar('pdf')} disabled={Boolean(descargando) || rangoInvalido}>
          {descargando === 'pdf' ? <Loader2 size={16} className="girar" /> : <FileText size={16} aria-hidden="true" />} PDF
        </button>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => exportar('excel')} disabled={Boolean(descargando) || rangoInvalido}>
          {descargando === 'excel' ? <Loader2 size={16} className="girar" /> : <FileSpreadsheet size={16} aria-hidden="true" />} Excel
        </button>
      </div>

      {rangoInvalido && <p className="mensaje-error" role="alert">La fecha de inicio no puede ser posterior a la final.</p>}
      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {/* Resumen */}
      {(cargando || resumen.length > 0) && (
        <div className="dash-estadisticas">
          {cargando && !datos
            ? Array.from({ length: 3 }, (_, i) => <TarjetaEstadistica key={i} cargando />)
            : resumen.map(([etiqueta, valor]) => (
                <TarjetaEstadistica
                  key={etiqueta}
                  titulo={etiqueta}
                  valor={typeof valor === 'number' ? (esResumenMonetario(etiqueta) ? formatearCOP(valor) : formatearNumero(valor)) : String(valor)}
                  icono={BarChart3}
                  tono={esResumenMonetario(etiqueta) ? 'verde' : 'dorado'}
                  cargando={cargando}
                />
              ))}
        </div>
      )}

      {/* Gráfica y tabla */}
      {cargando && !datos ? (
        <div className="tarjeta"><div className="esqueleto" style={{ height: 200 }} /></div>
      ) : datos && datos.filas.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <BarChart3 size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>Sin datos en este periodo</h2>
          <p className="texto-suave">Prueba con otro rango de fechas o con otro reporte.</p>
        </section>
      ) : (
        datos && (
          <>
            <GraficaReporte tipo={tipo} filas={datos.filas} />
            <TablaReporte key={`${tipo}-${desde}-${hasta}`} columnas={datos.columnas} columnasMoneda={datos.columnas_moneda} filas={datos.filas} />
          </>
        )
      )}
    </div>
  );
}