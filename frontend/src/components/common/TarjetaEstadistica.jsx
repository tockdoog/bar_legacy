// frontend/src/components/common/TarjetaEstadistica.jsx
// Tarjeta de indicador: título, valor grande, icono, variación porcentual
// frente a un periodo anterior (cuando existe) y un detalle opcional.

import { TrendingDown, TrendingUp } from 'lucide-react';

export default function TarjetaEstadistica({ titulo, valor, icono: Icono, variacion, detalle, cargando, tono = 'dorado' }) {
  // Bloque: mientras llegan los datos se muestra un esqueleto de carga
  if (cargando) {
    return (
      <div className="tarjeta tarjeta-compacta" aria-busy="true">
        <div className="esqueleto" style={{ height: 14, width: '55%' }} />
        <div className="esqueleto" style={{ height: 30, width: '80%', margin: '12px 0' }} />
        <div className="esqueleto" style={{ height: 12, width: '40%' }} />
      </div>
    );
  }

  const hayVariacion = typeof variacion === 'number' && Number.isFinite(variacion);
  const sube = hayVariacion && variacion >= 0;

  return (
    <div className="tarjeta tarjeta-compacta estadistica">
      <div className="estadistica-cabecera">
        <span className="texto-suave">{titulo}</span>
        {Icono && (
          <span className={`estadistica-icono tono-${tono}`}>
            <Icono size={18} aria-hidden="true" />
          </span>
        )}
      </div>
      <strong className="estadistica-valor">{valor}</strong>
      <div className="estadistica-pie">
        {hayVariacion && (
          <span className={`variacion ${sube ? 'sube' : 'baja'}`}>
            {sube ? <TrendingUp size={14} aria-hidden="true" /> : <TrendingDown size={14} aria-hidden="true" />}
            {Math.abs(variacion).toFixed(1).replace('.', ',')} %
          </span>
        )}
        {detalle && <span className="texto-suave">{detalle}</span>}
      </div>
    </div>
  );
}