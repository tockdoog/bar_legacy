// frontend/src/components/reportes/TablaReporte.jsx
// Tabla genérica de un reporte: columnas y filas llegan del backend, las
// columnas monetarias se muestran en COP y se pagina en el cliente. En móvil
// cada fila se convierte en tarjeta (ver catalogo.css). Debe montarse con una
// "key" distinta por reporte/periodo para volver a la primera página.

import Paginacion from '../common/Paginacion.jsx';
import usePaginacion from '../../hooks/usePaginacion.js';
import { formatearCOP } from '../../utils/formato.js';

export default function TablaReporte({ columnas, columnasMoneda, filas }) {
  const pag = usePaginacion(filas, 15);

  return (
    <div className="tarjeta tabla-contenedor">
      <table className="tabla-datos">
        <thead>
          <tr>
            {columnas.map((columna) => (
              <th key={columna} className={columnasMoneda.includes(columna) ? 'num' : ''}>{columna}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pag.items.map((fila, indice) => (
            <tr key={`${pag.pagina}-${indice}`}>
              {columnas.map((columna) => {
                const esMoneda = columnasMoneda.includes(columna);
                return (
                  <td key={columna} data-label={columna} className={esMoneda ? 'num' : ''}>
                    {esMoneda ? formatearCOP(fila[columna]) : String(fila[columna] ?? '—')}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <Paginacion pagina={pag.pagina} totalPaginas={pag.totalPaginas} total={pag.total} tamano={pag.tamano} onCambiar={pag.irAPagina} />
    </div>
  );
}