// frontend/src/components/usuarios/ModalRestablecer.jsx
// Ventana para que el administrador asigne una contraseña nueva a otro usuario
// (por ejemplo, si la olvidó). También le quita el bloqueo por intentos fallidos.

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import CampoContrasena from '../forms/CampoContrasena.jsx';
import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import { restablecerContrasena } from '../../services/modules/usuariosService.js';
import { AYUDA_CONTRASENA, validarContrasena } from '../../utils/contrasena.js';

export default function ModalRestablecer({ usuario, onCerrar }) {
  const [nueva, setNueva] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [errores, setErrores] = useState({});
  const [guardando, setGuardando] = useState(false);

  // Bloque: limpia el formulario cada vez que se abre para otro usuario
  useEffect(() => {
    setNueva('');
    setConfirmacion('');
    setErrores({});
    setGuardando(false);
  }, [usuario]);

  async function guardar(evento) {
    evento.preventDefault();
    const e = {};
    const problema = validarContrasena(nueva);
    if (problema) e.nueva = problema;
    if (nueva !== confirmacion) e.confirmacion = 'Las contraseñas no coinciden.';
    setErrores(e);
    if (Object.keys(e).length > 0) return;

    setGuardando(true);
    try {
      await restablecerContrasena(usuario.id, nueva);
      toast.success(`Contraseña de ${usuario.nombre_usuario} restablecida.`);
      onCerrar();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal abierto={Boolean(usuario)} onCerrar={onCerrar} titulo="Restablecer contraseña" ancho={440} bloqueado={guardando}>
      {usuario && (
        <form onSubmit={guardar} noValidate>
          <p>Nueva contraseña para <strong>{usuario.nombre_completo}</strong> (@{usuario.nombre_usuario}).</p>
          <CampoContrasena etiqueta="Contraseña nueva" valor={nueva} onCambiar={setNueva} error={errores.nueva} ayuda={AYUDA_CONTRASENA} autoFocus />
          <CampoContrasena etiqueta="Repite la contraseña" valor={confirmacion} onCambiar={setConfirmacion} error={errores.confirmacion} />
          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={guardando}>
              {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />} Restablecer
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}