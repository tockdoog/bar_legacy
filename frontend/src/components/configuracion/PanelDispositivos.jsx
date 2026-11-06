// frontend/src/components/configuracion/PanelDispositivos.jsx
// Sección "Dispositivos" (solo administrador): genera el código QR que permite
// abrir el sistema desde un celular o tablet en la red local. Solo aplica a
// instalaciones locales: en la nube el backend responde que no hay IP de red.

import { useState } from 'react';
import { Loader2, QrCode } from 'lucide-react';

import { mensajeDeError } from '../../services/api.js';
import { obtenerQrDispositivo } from '../../services/modules/configuracionService.js';

export default function PanelDispositivos() {
  const [qr, setQr] = useState(null);
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(false);

  async function generar() {
    setCargando(true);
    setError('');
    try {
      setQr(await obtenerQrDispositivo());
    } catch (fallo) {
      setQr(null);
      setError(mensajeDeError(fallo));
    } finally {
      setCargando(false);
    }
  }

  return (
    <section className="tarjeta" aria-labelledby="titulo-qr">
      <h3 id="titulo-qr"><QrCode size={18} aria-hidden="true" /> Vincular un dispositivo</h3>
      <p className="texto-suave">
        Escanea el código desde un celular o tablet conectado a la misma red Wi-Fi del servidor para abrir el sistema sin escribir la dirección.
        Esta opción solo funciona en instalaciones locales.
      </p>
      <button type="button" className="boton boton-primario" onClick={generar} disabled={cargando}>
        {cargando ? <Loader2 size={18} className="girar" aria-hidden="true" /> : <QrCode size={18} aria-hidden="true" />}
        {qr ? 'Generar de nuevo' : 'Generar código QR'}
      </button>

      {error && <p className="mensaje-error" role="alert">{error}</p>}
      {qr && (
        <div className="qr-resultado">
          <img src={qr.imagen_qr_base64} alt="Código QR con la dirección del sistema en la red local" width="220" height="220" />
          <p className="texto-suave">Dirección: <strong>{qr.url_acceso}</strong></p>
        </div>
      )}
    </section>
  );
}