// frontend/src/components/productos/CampoImagen.jsx
// Selector de imagen del producto: vista previa, validación de tipo y tamaño
// (las mismas reglas del backend: JPG, PNG o WEBP de hasta 5 MB) y opción de quitarla.

import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Package, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { urlImagen } from '../../services/api.js';

const TIPOS_PERMITIDOS = ['image/jpeg', 'image/png', 'image/webp'];
const TAMANO_MAXIMO = 5 * 1024 * 1024;

export default function CampoImagen({ imagenActual, archivo, quitada, onSeleccionar, onQuitar, deshabilitado }) {
  const entrada = useRef(null);
  const [vistaPrevia, setVistaPrevia] = useState(null);

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

  // Bloque: valida el archivo antes de aceptarlo
  function alElegir(evento) {
    const elegido = evento.target.files?.[0];
    evento.target.value = '';
    if (!elegido) return;
    if (!TIPOS_PERMITIDOS.includes(elegido.type)) {
      toast.error('Formato no permitido. Usa una imagen JPG, PNG o WEBP.');
      return;
    }
    if (elegido.size > TAMANO_MAXIMO) {
      toast.error('La imagen no puede superar los 5 MB.');
      return;
    }
    onSeleccionar(elegido);
  }

  return (
    <div className="imagen-campo">
      <div className="imagen-vista">
        {mostrada ? <img src={mostrada} alt="Vista previa del producto" /> : <Package size={30} aria-hidden="true" />}
      </div>
      <div className="imagen-acciones">
        <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp" onChange={alElegir} hidden />
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => entrada.current?.click()} disabled={deshabilitado}>
          <ImagePlus size={16} aria-hidden="true" /> {mostrada ? 'Cambiar imagen' : 'Agregar imagen'}
        </button>
        {mostrada && (
          <button type="button" className="boton boton-secundario boton-compacto" onClick={onQuitar} disabled={deshabilitado}>
            <Trash2 size={16} aria-hidden="true" /> Quitar
          </button>
        )}
        <small className="campo-ayuda">JPG, PNG o WEBP, máximo 5 MB.</small>
      </div>
    </div>
  );
}