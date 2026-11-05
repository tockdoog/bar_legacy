// frontend/src/components/promociones/TarjetaPromocionGestion.jsx
// Tarjeta de una promoción para la pantalla de gestión: nombre, estado,
// productos del combo, precio, ahorro del cliente y, solo si el backend los
// envía (administrador), costo, ganancia y margen. Un empleado recibe esos
// campos en null y no se muestran.

import { Package, Pencil, Power } from 'lucide-react';

import { urlImagen } from '../../services/api.js';
import { formatearCOP } from '../../utils/formato.js';

export default function TarjetaPromocionGestion({ promocion, esAdmin, onEditar, onAlternar }) {
  const veFinanzas = promocion.ganancia_negocio !== null && promocion.ganancia_negocio !== undefined;
  const enPerdida = veFinanzas && promocion.ganancia_negocio < 0;

  return (
    <article className={`tarjeta promo-tarjeta ${promocion.activa ? '' : 'inactiva'}`}>
      <header className="promo-cabecera">
        <h3>{promocion.nombre}</h3>
        <span className={`etiqueta ${promocion.activa ? 'verde' : 'gris'}`}>{promocion.activa ? 'Activa' : 'Inactiva'}</span>
      </header>
      {promocion.descripcion && <p className="texto-suave promo-descripcion">{promocion.descripcion}</p>}

      {/* Productos que forman el combo */}
      <ul className="promo-componentes">
        {promocion.componentes.map((c) => {
          const imagen = urlImagen(c.imagen_url);
          return (
            <li key={c.producto_id}>
              <span className="miniatura miniatura-chica">
                {imagen ? <img src={imagen} alt="" loading="lazy" /> : <Package size={16} aria-hidden="true" />}
              </span>
              <span>{c.cantidad} × {c.nombre_producto}</span>
            </li>
          );
        })}
      </ul>

      {/* Precios y ahorro del cliente */}
      <div className="promo-precio">
        <strong>{formatearCOP(promocion.precio_promocional)}</strong>
        <span className="texto-suave promo-tachado">{formatearCOP(promocion.valor_normal)}</span>
        {promocion.ahorro_cliente > 0 ? (
          <span className="etiqueta verde">Ahorra {formatearCOP(promocion.ahorro_cliente)} ({promocion.porcentaje_descuento.toFixed(0)} %)</span>
        ) : (
          <span className="etiqueta ambar">Sin ahorro para el cliente</span>
        )}
      </div>

      {/* Datos financieros: solo llegan al administrador */}
      {veFinanzas && (
        <dl className={`promo-finanzas ${enPerdida ? 'perdida' : ''}`}>
          <div><dt>Costo</dt><dd>{formatearCOP(promocion.costo_total)}</dd></div>
          <div><dt>Ganancia</dt><dd>{formatearCOP(promocion.ganancia_negocio)}</dd></div>
          <div><dt>Margen</dt><dd>{promocion.margen_ganancia_porcentaje.toFixed(1).replace('.', ',')} %</dd></div>
        </dl>
      )}

      <p className="texto-suave promo-vigencia">
        {promocion.activa ? 'Vigente mientras esté activa.' : 'No disponible en el punto de venta.'}
      </p>

      {esAdmin && (
        <footer className="promo-acciones">
          <button type="button" className="boton boton-secundario boton-compacto" onClick={() => onEditar(promocion)}>
            <Pencil size={15} aria-hidden="true" /> Editar
          </button>
          <button type="button" className="boton boton-secundario boton-compacto" onClick={() => onAlternar(promocion)}>
            <Power size={15} aria-hidden="true" /> {promocion.activa ? 'Desactivar' : 'Activar'}
          </button>
        </footer>
      )}
    </article>
  );
}