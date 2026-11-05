// frontend/src/hooks/useLectorCodigoBarras.js
// Detecta lectores USB de código de barras, que funcionan como un teclado:
// escriben el código muy rápido y terminan con Enter. Se distingue de una
// persona escribiendo por la velocidad entre teclas. Ignora lo que se escribe
// dentro de campos de texto (esos los maneja cada campo).

import { useEffect, useRef } from 'react';

const PAUSA_MAXIMA_MS = 80; // Más lento que esto se considera escritura humana
const LARGO_MINIMO = 4;

export default function useLectorCodigoBarras(alLeer, activo = true) {
  // Se guarda la última función recibida sin reiniciar el listener en cada render
  const funcion = useRef(alLeer);
  funcion.current = alLeer;

  useEffect(() => {
    if (!activo) return undefined;

    let acumulado = '';
    let ultimaTecla = 0;

    const alTeclear = (evento) => {
      const destino = evento.target;
      const enCampo =
        destino &&
        (['INPUT', 'TEXTAREA', 'SELECT'].includes(destino.tagName) || destino.isContentEditable);
      if (enCampo || evento.ctrlKey || evento.metaKey || evento.altKey) return;

      const ahora = performance.now();
      if (ahora - ultimaTecla > PAUSA_MAXIMA_MS) acumulado = '';
      ultimaTecla = ahora;

      if (evento.key === 'Enter') {
        if (acumulado.length >= LARGO_MINIMO) {
          evento.preventDefault();
          const codigo = acumulado;
          acumulado = '';
          funcion.current(codigo);
        }
        acumulado = '';
        return;
      }
      // Solo caracteres válidos en un código de barras (letras, números y guiones)
      if (/^[A-Za-z0-9-]$/.test(evento.key)) acumulado += evento.key;
    };

    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [activo]);
}