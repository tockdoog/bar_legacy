// frontend/src/components/common/GraficaBarras.jsx
// Gráfica de barras ligera en SVG (sin librerías externas). Es responsive,
// muestra el valor de cada barra al pasar el cursor y adapta la cantidad de
// etiquetas del eje horizontal para que no se superpongan.

export default function GraficaBarras({ datos, formatoValor = String, descripcion = 'Gráfica de barras' }) {
  // Bloque: dimensiones internas del dibujo (el SVG se escala al ancho disponible)
  const ANCHO = 640;
  const ALTO = 210;
  const MARGEN_INFERIOR = 28;
  const MARGEN_SUPERIOR = 14;

  const maximo = Math.max(...datos.map((d) => d.valor), 1);
  const alturaUtil = ALTO - MARGEN_INFERIOR - MARGEN_SUPERIOR;
  const paso = ANCHO / datos.length;
  const anchoBarra = Math.min(36, paso * 0.62);
  const salto = datos.length > 16 ? 3 : datos.length > 8 ? 2 : 1;

  return (
    <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} role="img" aria-label={descripcion} className="grafica">
      {/* Líneas guía horizontales (0 %, 50 % y 100 %) */}
      {[0, 0.5, 1].map((fraccion) => {
        const y = MARGEN_SUPERIOR + alturaUtil * (1 - fraccion);
        return <line key={fraccion} x1="0" x2={ANCHO} y1={y} y2={y} className="grafica-guia" />;
      })}

      {/* Barras con su valor como texto emergente y etiqueta de fecha */}
      {datos.map((dato, indice) => {
        const alto = dato.valor > 0 ? Math.max((alturaUtil * dato.valor) / maximo, 2) : 0;
        const x = indice * paso + (paso - anchoBarra) / 2;
        const y = ALTO - MARGEN_INFERIOR - alto;
        return (
          <g key={`${dato.etiqueta}-${indice}`}>
            <rect x={x} y={y} width={anchoBarra} height={alto} rx="4" className="grafica-barra">
              <title>{`${dato.etiqueta}: ${formatoValor(dato.valor)}`}</title>
            </rect>
            {indice % salto === 0 && (
              <text x={x + anchoBarra / 2} y={ALTO - 9} textAnchor="middle" className="grafica-texto">
                {dato.etiqueta}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}