// frontend/src/components/common/Confirmar.jsx
// Diálogo de confirmación que reemplaza a window.confirm(). Se usa antes de
// acciones destructivas (vaciar carrito, cancelar cuenta, eliminar mesa).

import { Loader2 } from 'lucide-react';

import Modal from './Modal.jsx';

export default function Confirmar({
  abierto,
  titulo,
  mensaje,
  textoConfirmar = 'Confirmar',
  peligro = false,
  cargando = false,
  onConfirmar,
  onCancelar,
}) {
  return (
    <Modal abierto={abierto} onCerrar={onCancelar} titulo={titulo} ancho={420} bloqueado={cargando}>
      <p>{mensaje}</p>
      <div className="modal-acciones">
        <button type="button" className="boton boton-secundario" onClick={onCancelar} disabled={cargando}>
          Cancelar
        </button>
        <button
          type="button"
          className={`boton ${peligro ? 'boton-peligro' : 'boton-primario'}`}
          onClick={onConfirmar}
          disabled={cargando}
        >
          {cargando && <Loader2 size={18} className="girar" aria-hidden="true" />}
          {textoConfirmar}
        </button>
      </div>
    </Modal>
  );
}