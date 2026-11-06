// frontend/src/components/productos/CampoImagen.jsx
// Selector de imagen del producto: vista previa, validación de tipo (JPG, PNG o
// WEBP), optimización automática en el navegador (ver utils/imagen.js) y opción
// de quitarla. Acepta originales de hasta 15 MB porque se reducen antes de subir.

import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Loader2, Package, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { urlImagen } from '../../services/api.js';
import { comprimirImagen } from '../../utils/imagen.js';

const TIPOS_PERMITIDOS = ['image/jpeg', 'image/png', 'image/webp'];
const TAMANO_MAXIMO_ORIGINAL = 15 * 1024 * 1024;

export default function CampoImagen({ imagenActual, archivo, quitada, onSeleccionar, onQuitar, deshabilitado }) {
  const entrada = useRef(null);
  const [vistaPrevia, setVistaPrevia] = useState(null);
  const [procesando, setProcesando] = useState(false);

  // Bloque: crea y libera la URL temporal de la vista previa del archivo elegido
  useEffect(() => {
    if (!archivo) {
      setVistaPrevia(null);
      return undefined;
    }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  const mostrada = vistaPrevia || (!quitada ? urlImagen(imagenActual) : null);

  // Bloque: valida el archivo, lo optimiza y lo entrega al formulario
  async function alElegir(evento) {
    const elegido = evento.target.files?.[0];
    evento.target.value = '';
    if (!elegido) return;
    if (!TIPOS_PERMITIDOS.includes(elegido.type)) {
      toast.error('Formato no permitido. Usa una imagen JPG, PNG o WEBP.');
      return;
    }
    if (elegido.size > TAMANO_MAXIMO_ORIGINAL) {
      toast.error('La imagen original no puede superar los 15 MB.');
      return;
    }
    setProcesando(true);
    try {
      onSeleccionar(await comprimirImagen(elegido));
    } catch {
      toast.error('No se pudo procesar la imagen. Prueba con otra.');
    } finally {
      setProcesando(false);
    }
  }

  const bloqueado = deshabilitado || procesando;

  return (
    <div className="imagen-campo">
      <div className="imagen-vista">
        {mostrada ? <img src={mostrada} alt="Vista previa del producto" /> : <Package size={30} aria-hidden="true" />}
      </div>
      <div className="imagen-acciones">
        <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp" onChange={alElegir} hidden />
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => entrada.current?.click()} disabled={bloqueado}>
          {procesando ? <Loader2 size={16} className="girar" aria-hidden="true" /> : <ImagePlus size={16} aria-hidden="true" />}
          {procesando ? 'Procesando…' : mostrada ? 'Cambiar imagen' : 'Agregar imagen'}
        </button>
        {mostrada && (
          <button type="button" className="boton boton-secundario boton-compacto" onClick={onQuitar} disabled={bloqueado}>
            <Trash2 size={16} aria-hidden="true" /> Quitar
          </button>
        )}
        <small className="campo-ayuda">JPG, PNG o WEBP. Se optimiza automáticamente antes de subirla.</small>
      </div>
    </div>
  );
}