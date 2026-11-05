// frontend/src/components/pos/EscanerCamara.jsx
// Escáner de códigos de barras con la cámara del dispositivo. Usa la API nativa
// BarcodeDetector (Chrome y Edge en Android y escritorio). Si el navegador no la
// ofrece (por ejemplo Safari en iPhone), lo informa y sugiere usar un lector USB
// o escribir el código. La cámara se apaga siempre al cerrar.

import { useEffect, useRef, useState } from 'react';

import Modal from '../common/Modal.jsx';

const FORMATOS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39'];

// Bloque: indica si este navegador puede escanear con la cámara
export const camaraSoportada = () =>
  typeof window !== 'undefined' &&
  'BarcodeDetector' in window &&
  Boolean(navigator.mediaDevices?.getUserMedia);

// Bloque: visor que enciende la cámara mientras está montado
function Visor({ onCodigo }) {
  const video = useRef(null);
  const alLeer = useRef(onCodigo);
  alLeer.current = onCodigo;
  const [error, setError] = useState('');

  useEffect(() => {
    let activo = true;
    let flujo = null;
    let temporizador = null;

    async function iniciar() {
      try {
        if (!camaraSoportada()) throw new Error('sin-soporte');
        flujo = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        });
        if (!activo) {
          flujo.getTracks().forEach((pista) => pista.stop());
          return;
        }
        video.current.srcObject = flujo;
        await video.current.play();

        const detector = new window.BarcodeDetector({ formats: FORMATOS });
        temporizador = setInterval(async () => {
          try {
            const resultados = await detector.detect(video.current);
            if (resultados.length && activo) {
              activo = false;
              alLeer.current(resultados[0].rawValue);
            }
          } catch {
            // Un cuadro sin código legible no es un error
          }
        }, 350);
      } catch (fallo) {
        setError(
          fallo?.name === 'NotAllowedError'
            ? 'No diste permiso para usar la cámara. Actívalo en los permisos del navegador.'
            : 'Este navegador no permite escanear con la cámara. Usa un lector USB o escribe el código.'
        );
      }
    }
    iniciar();

    return () => {
      activo = false;
      clearInterval(temporizador);
      flujo?.getTracks().forEach((pista) => pista.stop());
    };
  }, []);

  if (error) return <p className="mensaje-error" role="alert">{error}</p>;
  return (
    <div className="camara-visor">
      <video ref={video} playsInline muted aria-label="Vista de la cámara" />
      <span className="camara-guia" aria-hidden="true" />
      <p className="texto-suave">Apunta la cámara al código de barras.</p>
    </div>
  );
}

export default function EscanerCamara({ abierto, onCerrar, onCodigo }) {
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Escanear con la cámara" ancho={460}>
      {abierto && (
        <Visor
          onCodigo={(codigo) => {
            onCerrar();
            onCodigo(codigo);
          }}
        />
      )}
    </Modal>
  );
}