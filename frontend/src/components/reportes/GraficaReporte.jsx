// frontend/src/components/reportes/GraficaReporte.jsx
// Gráfica según el tipo de reporte: barras por día (ventas, compras y
// ganancias, estas con selector de métrica) y ranking horizontal (más y menos
// vendidos). Los demás reportes no llevan gráfica.

import { useMemo, useState } from 'react';

import GraficaBarras from '../common/GraficaBarras.jsx';
import { formatearCOP, formatearNumero } from '../../utils/formato.js';
import { serieSumaPorDia } from '../../utils/reportes.js';

// Bloque: reportes que se grafican por día y la métrica que suman
const POR_DIA = {
  ventas: { campo: 'Total', titulo: 'Ventas por día' },
  compras: { campo: 'Subtotal', titulo: 'Compras por día' },
  ganancias: { campo: 'Ventas', titulo: 'Evolución diaria' },
};

export default function GraficaReporte({ tipo, filas }) {
  const [metrica, setMetrica] = useState('Ventas');
  const configuracion = POR_DIA[tipo];
  const campo = tipo === 'ganancias' ? metrica : configuracion?.campo;

  const serie = useMemo(() => (configuracion ? serieSumaPorDia(filas, campo) : []), [configuracion, filas, campo]);

  // Bloque: ranking de productos (más y menos vendidos)
  if (tipo === 'mas-vendidos' || tipo === 'menos-vendidos') {
    if (filas.length === 0) return null;
    const maximo = Math.max(...filas.map((f) => f['Cantidad vendida']), 1);
    return (
      <section className="tarjeta tarjeta-compacta" aria-label="Ranking de productos">
        <h3>{tipo === 'mas-vendidos' ? 'Ranking: más vendidos' : 'Ranking: menos vendidos'}</h3>
        <ol className="lista-ranking">
          {filas.map((fila, indice) => (
            <li key={`${fila.Producto}-${indice}`}>
              <div className="ranking-linea">
                <span>{fila.Producto}</span>
                <strong>{formatearNumero(fila['Cantidad vendida'])} u. · {formatearCOP(fila['Total vendido'])}</strong>
              </div>
              <div className="ranking-barra">
                <span style={{ width: `${(fila['Cantidad vendida'] / maximo) * 100}%` }} />
              </div>
            </li>
          ))}
        </ol>
      </section>
    );
  }

  // Bloque: barras por día
  if (!configuracion || serie.length === 0 || !serie.some((punto) => punto.valor > 0)) return null;
  return (
    <section className="tarjeta tarjeta-compacta" aria-label={configuracion.titulo}>
      <div className="dash-seccion-cabecera">
        <h3>{configuracion.titulo}</h3>
        {tipo === 'ganancias' && (
          <div className="selector-periodo" role="group" aria-label="Métrica de la gráfica">
            {['Ventas', 'Costo', 'Ganancia'].map((nombre) => (
              <button key={nombre} type="button" className={metrica === nombre ? 'activo' : ''} onClick={() => setMetrica(nombre)}>
                {nombre}
              </button>
            ))}
          </div>
        )}
      </div>
      <GraficaBarras datos={serie} formatoValor={formatearCOP} descripcion={`${configuracion.titulo} (${campo})`} />
    </section>
  );
}