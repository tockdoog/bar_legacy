// frontend/src/components/configuracion/PanelSuscripcion.jsx
// Estado de la suscripción mensual. El administrador, además, ve las cuentas de
// pago del proveedor y puede desbloquear el sistema con la clave maestra
// (entregada por el proveedor tras confirmar el pago). Se usa en Configuración
// y en la pantalla de bloqueo.
// CAMBIO: el backend ya guarda las fechas en hora de Bogotá, se muestran tal cual.

import { useEffect, useState } from 'react';
import { CalendarClock, Copy, Loader2, Unlock } from 'lucide-react';
import { toast } from 'sonner';

import { mensajeDeError, urlImagen } from '../../services/api.js';
import { desbloquearSistema, listarCuentasPago } from '../../services/modules/suscripcionService.js';
import { formatearCOP, formatearFecha } from '../../utils/formato.js';

export default function PanelSuscripcion({ estado, esAdmin, onActualizado }) {
  const [cuentas, setCuentas] = useState([]);
  const [errorCuentas, setErrorCuentas] = useState('');
  const [clave, setClave] = useState('');
  const [errorClave, setErrorClave] = useState('');
  const [enviando, setEnviando] = useState(false);

  // Bloque: las cuentas de pago solo se piden al administrador
  useEffect(() => {
    if (!esAdmin) return;
    listarCuentasPago()
      .then(setCuentas)
      .catch((fallo) => setErrorCuentas(mensajeDeError(fallo)));
  }, [esAdmin]);

  // Bloque: copia un dato de pago al portapapeles
  async function copiar(valor) {
    try {
      await navigator.clipboard.writeText(valor);
      toast.success('Copiado al portapapeles.', { duration: 1500 });
    } catch {
      toast.error('No se pudo copiar. Selecciona el texto manualmente.');
    }
  }

  // Bloque: desbloquea con la clave maestra; si es incorrecta muestra el mensaje del backend
  async function desbloquear(evento) {
    evento.preventDefault();
    if (!clave.trim()) {
      setErrorClave('Escribe la clave de desbloqueo.');
      return;
    }
    setEnviando(true);
    setErrorClave('');
    try {
      const nuevoEstado = await desbloquearSistema(clave);
      toast.success(nuevoEstado.mensaje || 'Sistema desbloqueado.');
      setClave('');
      onActualizado?.(nuevoEstado);
    } catch (fallo) {
      setErrorClave(mensajeDeError(fallo));
      setClave('');
    } finally {
      setEnviando(false);
    }
  }

  if (!estado) return <div className="tarjeta"><div className="esqueleto" style={{ height: 120 }} /></div>;

  return (
    <div className="suscripcion">
      {/* Estado del ciclo de pago */}
      <section className="tarjeta" aria-labelledby="titulo-estado-pago">
        <h3 id="titulo-estado-pago"><CalendarClock size={18} aria-hidden="true" /> Estado de la suscripción</h3>
        <dl className="detalle-datos">
          <div>
            <dt>Estado</dt>
            <dd><span className={`etiqueta ${estado.bloqueado ? 'rojo' : estado.dias_restantes <= 3 ? 'ambar' : 'verde'}`}>
              {estado.bloqueado ? 'Bloqueado' : `${estado.dias_restantes} día(s) restante(s)`}
            </span></dd>
          </div>
          <div><dt>Vence</dt><dd>{formatearFecha(estado.fecha_vencimiento)}</dd></div>
          {estado.valor_mensual_cop > 0 && <div><dt>Valor mensual</dt><dd>{formatearCOP(estado.valor_mensual_cop)}</dd></div>}
        </dl>
        {estado.mensaje && <p className={`aviso-form ${estado.bloqueado ? 'critico' : ''}`}>{estado.mensaje}</p>}
      </section>

      {/* Cuentas de pago y desbloqueo: solo administrador */}
      {esAdmin && (
        <>
          <section className="tarjeta" aria-labelledby="titulo-cuentas">
            <h3 id="titulo-cuentas">Cómo pagar</h3>
            {errorCuentas && <p className="mensaje-error" role="alert">{errorCuentas}</p>}
            <div className="cuentas-rejilla">
              {cuentas.map((cuenta) => {
                const imagen = urlImagen(cuenta.imagen_url);
                return (
                  <article key={cuenta.nombre} className="cuenta-tarjeta">
                    <strong>{cuenta.nombre}</strong>
                    <span className="texto-suave">{cuenta.tipo_dato}</span>
                    <span className="cuenta-valor">
                      {cuenta.valor}
                      <button type="button" className="boton-icono" onClick={() => copiar(cuenta.valor)} aria-label={`Copiar ${cuenta.tipo_dato} de ${cuenta.nombre}`}>
                        <Copy size={16} />
                      </button>
                    </span>
                    {imagen && <img src={imagen} alt={`Código QR de ${cuenta.nombre}`} loading="lazy" />}
                  </article>
                );
              })}
            </div>
          </section>

          <section className="tarjeta" aria-labelledby="titulo-desbloqueo">
            <h3 id="titulo-desbloqueo"><Unlock size={18} aria-hidden="true" /> Renovar o desbloquear</h3>
            <p className="texto-suave">Después de pagar, el proveedor te entrega una clave. Al ingresarla se renueva la suscripción.</p>
            <form onSubmit={desbloquear} noValidate className="desbloqueo-form">
              <div className={`campo-caja ${errorClave ? 'con-error' : ''}`}>
                <input
                  type="password"
                  value={clave}
                  onChange={(e) => setClave(e.target.value)}
                  placeholder="Clave de desbloqueo"
                  autoComplete="off"
                  maxLength={255}
                  aria-label="Clave de desbloqueo"
                />
              </div>
              <button type="submit" className="boton boton-primario" disabled={enviando}>
                {enviando && <Loader2 size={18} className="girar" aria-hidden="true" />} Desbloquear
              </button>
            </form>
            {errorClave && <small className="campo-error" role="alert">{errorClave}</small>}
          </section>
        </>
      )}
    </div>
  );
}