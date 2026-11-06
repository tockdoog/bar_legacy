// frontend/src/hooks/useBloqueoMesa.js
// Mantiene el bloqueo colaborativo de una mesa mientras el usuario atiende su
// cuenta: lo toma al entrar, lo renueva cada 20 s (latido) y lo libera al salir.
// Si otro usuario ya la atiende, devuelve la situación "ocupado" con el mensaje
// del servidor y sigue intentando: si el otro sale, el bloqueo pasa a este usuario.
// Un fallo de red no cambia la situación (el servidor expira los bloqueos solos).

import { useEffect, useState } from 'react';

import { mensajeDeError } from '../services/api.js';
import { liberarBloqueoAlSalir, tomarBloqueo } from '../services/modules/mesasService.js';

const INTERVALO_LATIDO_MS = 20000;
const INICIAL = { situacion: 'sin-mesa', mensaje: '' };

// situacion: 'sin-mesa' | 'verificando' | 'propio' | 'ocupado'
export default function useBloqueoMesa(mesaId, activo = true) {
  const [estado, setEstado] = useState(INICIAL);

  useEffect(() => {
    if (!mesaId || !activo) {
      setEstado(INICIAL);
      return undefined;
    }

    let vigente = true;
    const tomar = async () => {
      try {
        await tomarBloqueo(mesaId);
        if (vigente) setEstado({ situacion: 'propio', mensaje: '' });
      } catch (error) {
        if (vigente && error.response?.status === 409) {
          setEstado({ situacion: 'ocupado', mensaje: mensajeDeError(error) });
        }
      }
    };

    setEstado({ situacion: 'verificando', mensaje: '' });
    tomar();
    const temporizador = setInterval(tomar, INTERVALO_LATIDO_MS);

    return () => {
      vigente = false;
      clearInterval(temporizador);
      liberarBloqueoAlSalir(mesaId);
    };
  }, [mesaId, activo]);

  return estado;
}