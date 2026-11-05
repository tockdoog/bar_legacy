// frontend/src/components/compras/DetalleCompra.jsx
// Ventana de solo lectura con el detalle de una compra: proveedor, fecha,
// productos con cantidad, costo unitario y subtotal, y el total.

import Modal from '../common/Modal.jsx';
import { formatearCOP, formatearFecha, formatearNumero } from '../../utils/formato.js';

export default function DetalleCompra({ compra, onCerrar }) {
  return (
    <Modal abierto={Boolean(compra)} onCerrar={onCerrar} titulo={compra ? `Compra #${compra.id}` : 'Compra'} ancho={620}>
      {compra && (
        <>
          <dl className="detalle-datos">
            <div><dt>Proveedor</dt><dd>{compra.nombre_proveedor}</dd></div>
            <div><dt>Fecha</dt><dd>{formatearFecha(compra.fecha)}</dd></div>
          </dl>

          <div className="tabla-contenedor detalle-tabla">
            <table className="tabla-datos">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="num">Cantidad</th>
                  <th className="num">Costo unitario</th>
                  <th className="num">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {compra.detalles.map((d) => (
                  <tr key={d.id}>
                    <td><strong>{d.nombre_producto}</strong></td>
                    <td data-label="Cantidad" className="num">{formatearNumero(d.cantidad)}</td>
                    <td data-label="Costo unitario" className="num">{formatearCOP(d.costo_unitario)}</td>
                    <td data-label="Subtotal" className="num">{formatearCOP(d.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="compra-total">
            <span>Total</span>
            <strong>{formatearCOP(compra.total)}</strong>
          </div>
          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={onCerrar}>Cerrar</button>
          </div>
        </>
      )}
    </Modal>
  );
}