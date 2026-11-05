// frontend/src/components/pos/Tirilla.jsx
// Tirilla de la factura para impresoras térmicas de 80 mm. Se dibuja en un
// portal fuera de la aplicación: en pantalla está oculta y solo aparece al
// imprimir (ver reglas @media print en componentes.css).

import { createPortal } from 'react-dom';

import { formatearCOP, formatearFecha } from '../../utils/formato.js';

export default function Tirilla({ datos }) {
  if (!datos) return null;
  const { negocio, venta, items, totales, grupos_impuesto: grupos, proveedor } = datos;

  return createPortal(
    <div className="tirilla-portal" aria-hidden="true">
      <div className="tirilla">
        {/* Encabezado con los datos del negocio */}
        <div className="tirilla-centro">
          <strong>{negocio.nombre}</strong>
          {negocio.nit && <div>{negocio.nit}</div>}
          {negocio.direccion && <div>{negocio.direccion}</div>}
          {negocio.telefono && <div>{negocio.telefono}</div>}
        </div>
        <hr />
        <div>Factura de venta #{venta.id}</div>
        <div>Fecha: {formatearFecha(venta.fecha)}</div>
        {venta.mesa && <div>Mesa: {venta.mesa}</div>}
        <div>Atendido por: {venta.vendedor}</div>
        {venta.estado === 'anulada' && <div><strong>VENTA ANULADA</strong></div>}
        <hr />

        {/* Detalle de productos */}
        {items.map((item, indice) => (
          <div key={`${item.nombre}-${indice}`} className="tirilla-item">
            <div>{item.nombre}</div>
            <div className="tirilla-fila">
              <span>{item.cantidad} x {formatearCOP(item.precio_unitario)}</span>
              <span>{formatearCOP(item.subtotal)}</span>
            </div>
          </div>
        ))}
        <hr />

        {/* Discriminación del impuesto, solo de los grupos que sí lo aplican */}
        {grupos.filter((g) => g.aplica).map((g) => (
          <div key={`${g.etiqueta}-${g.porcentaje}`}>
            <div className="tirilla-fila"><span>Base gravable</span><span>{formatearCOP(g.base_gravable)}</span></div>
            <div className="tirilla-fila"><span>{g.etiqueta} ({g.porcentaje}%)</span><span>{formatearCOP(g.valor_impuesto)}</span></div>
          </div>
        ))}

        {/* Totales y pago */}
        <div className="tirilla-fila tirilla-total"><span>TOTAL</span><span>{formatearCOP(totales.total)}</span></div>
        <div className="tirilla-fila"><span>Método</span><span>{totales.metodo_pago}</span></div>
        <div className="tirilla-fila"><span>Pagó con</span><span>{formatearCOP(totales.monto_pagado)}</span></div>
        <div className="tirilla-fila"><span>Cambio</span><span>{formatearCOP(totales.cambio)}</span></div>
        <hr />
        <div className="tirilla-centro">
          <div>¡Gracias por su compra!</div>
          <div>{proveedor.nombre}</div>
        </div>
      </div>
    </div>,
    document.body
  );
}