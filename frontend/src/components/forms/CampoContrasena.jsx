// frontend/src/components/forms/CampoContrasena.jsx
// Campo de contraseña con botón para mostrar u ocultar el texto. Lo comparten
// el formulario de usuarios, el restablecimiento y el cambio de contraseña propia.

import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

import Campo from './Campo.jsx';

export default function CampoContrasena({
  etiqueta,
  valor,
  onCambiar,
  error,
  ayuda,
  autoComplete = 'new-password',
  autoFocus = false,
}) {
  const [visible, setVisible] = useState(false);

  return (
    <Campo etiqueta={etiqueta} error={error} ayuda={ayuda}>
      <input
        type={visible ? 'text' : 'password'}
        value={valor}
        onChange={(e) => onCambiar(e.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        maxLength={72}
      />
      <button
        type="button"
        className="boton-icono"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </Campo>
  );
}