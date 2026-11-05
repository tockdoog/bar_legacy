// frontend/src/components/pos/ModalExito.jsx
// Confirmación de venta cobrada: destaca el cambio a devolver y ofrece las tres
// opciones de factura del backend: imprimir tirilla, descargar PDF y enviar por
// correo. Anima el check de confirmación.

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Download, Loader2, Mail, Printer } from 'lucide-react';
import { toast } from 'sonner';

import Modal from '../common/Modal.jsx';
import Tirilla from './Tirilla.jsx';
import { mensajeDeError } from '../../services/api.js';
import {
  descargarFacturaPdf,
  enviarFacturaCorreo,
  obtenerDatosFactura,
} from '../../services/modules/ventasService.js';
import { formatearCOP } from '../../utils/formato.js';

const FORMATO_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ModalExito({ venta, onNueva }) {
  const [datosFactura, setDatosFactura] = useState(null);
  const [correo, setCorreo] = useState('');
  const [ocupado, setOcupado] = useState('');

  // Bloque: al cobrar, carga los datos de la factura para poder imprimir la tirilla
  useEffect(() => {
    setDatosFactura(null);
    setCorreo('');
    if (!venta) return;
    obtenerDatosFactura(venta.id)
      .then(setDatosFactura)
      .catch((error) => toast.error(mensajeDeError(error)));
  }, [venta]);

  // Bloque: ejecuta una acción de factura mostrando el estado de carga
  async function accion(nombre, tarea, mensajeOk) {
    setOcupado(nombre);
    try {
      await tarea();
      if (mensajeOk) toast.success(mensajeOk);
    } catch (error) {
      toast.error(mensajeDeError(error));
    } finally {
      setOcupado('');
    }
  }

  const enviarCorreo = (evento) => {
    evento.preventDefault();
    if (!FORMATO_CORREO.test(correo.trim())) {
      toast.error('Escribe un correo electrónico válido.');
      return;
    }
    accion('correo', () => enviarFacturaCorreo(venta.id, correo.trim()), 'Factura enviada correctamente.');
  };

  return (
    <Modal abierto={Boolean(venta)} onCerrar={onNueva} titulo="Venta registrada" ancho={480}>
      {venta && (
        <>
          <div className="exito-cabecera">
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 16 }}>
              <CheckCircle2 size={56} color="var(--verde)" aria-hidden="true" />
            </motion.span>
            <p className="texto-suave">Venta #{venta.id} cobrada</p>
            <strong className="exito-total">{formatearCOP(venta.total)}</strong>
          </div>

          <dl className="cobro-resumen">
            <div><dt>Recibido</dt><dd>{formatearCOP(venta.monto_pagado)}</dd></div>
            <div className="cambio"><dt>Cambio a devolver</dt><dd>{formatearCOP(venta.cambio)}</dd></div>
          </dl>

          <div className="exito-botones">
            <button type="button" className="boton boton-secundario" disabled={!datosFactura} onClick={() => window.print()}>
              <Printer size={18} aria-hidden="true" /> Imprimir tirilla
            </button>
            <button
              type="button"
              className="boton boton-secundario"
              disabled={ocupado === 'pdf'}
              onClick={() => accion('pdf', () => descargarFacturaPdf(venta.id))}
            >
              {ocupado === 'pdf' ? <Loader2 size={18} className="girar" /> : <Download size={18} aria-hidden="true" />}
              Descargar PDF
            </button>
          </div>

          <form className="exito-correo" onSubmit={enviarCorreo} noValidate>
            <div className="campo-caja">
              <Mail size={18} aria-hidden="true" />
              <input
                type="email"
                placeholder="Correo del cliente (opcional)"
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
                autoComplete="off"
                aria-label="Correo del cliente"
              />
            </div>
            <button type="submit" className="boton boton-secundario" disabled={ocupado === 'correo' || !correo.trim()}>
              {ocupado === 'correo' && <Loader2 size={18} className="girar" aria-hidden="true" />}
              Enviar
            </button>
          </form>

          <button type="button" className="boton boton-primario boton-completo" onClick={onNueva} autoFocus>
            Nueva venta
          </button>
          <Tirilla datos={datosFactura} />
        </>
      )}
    </Modal>
  );
}