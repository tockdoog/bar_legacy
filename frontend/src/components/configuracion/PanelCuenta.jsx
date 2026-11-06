// frontend/src/components/configuracion/PanelCuenta.jsx
// Sección "Mi cuenta": datos de la sesión (nombre, rol y permisos) y cambio de la
// propia contraseña. El backend exige la contraseña actual y devuelve un error
// claro si no coincide.

import { useState } from 'react';
import { Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import CampoContrasena from '../forms/CampoContrasena.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { mensajeDeError } from '../../services/api.js';
import { cambiarMiContrasenaServicio } from '../../services/modules/authService.js';
import { AYUDA_CONTRASENA, validarContrasena } from '../../utils/contrasena.js';

// Bloque: nombres legibles de los permisos, solo para mostrarlos. Si el backend suma
// uno nuevo, se muestra su clave. La fuente de verdad sigue siendo permisos.py.
const NOMBRES_PERMISOS = {
  inventario_gestionar: 'Gestionar el inventario',
  compras_gestionar: 'Compras y proveedores',
  ventas_anular: 'Anular ventas cobradas',
  reportes_ver: 'Ver reportes',
  finanzas_gestionar: 'Impuestos y análisis financiero',
};

export default function PanelCuenta() {
  const { usuario, esAdmin } = useAuth();
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [errores, setErrores] = useState({});
  const [guardando, setGuardando] = useState(false);

  async function guardar(evento) {
    evento.preventDefault();
    const e = {};
    if (!actual) e.actual = 'Escribe tu contraseña actual.';
    const problema = validarContrasena(nueva);
    if (problema) e.nueva = problema;
    else if (nueva === actual) e.nueva = 'Debe ser distinta a la actual.';
    if (nueva !== confirmacion) e.confirmacion = 'Las contraseñas no coinciden.';
    setErrores(e);
    if (Object.keys(e).length > 0) return;

    setGuardando(true);
    try {
      await cambiarMiContrasenaServicio(actual, nueva);
      toast.success('Contraseña actualizada.');
      setActual('');
      setNueva('');
      setConfirmacion('');
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="config-dos">
      <section className="tarjeta" aria-labelledby="titulo-datos">
        <h3 id="titulo-datos">Mi sesión</h3>
        <p><strong>{usuario.nombre_completo}</strong></p>
        <p className="texto-suave"><ShieldCheck size={14} aria-hidden="true" /> {esAdmin ? 'Administrador (acceso completo)' : 'Empleado'}</p>
        {!esAdmin && (
          <>
            <p className="texto-suave">Permisos adicionales:</p>
            {usuario.permisos.length === 0 ? (
              <p className="texto-suave">Solo ventas y consulta de inventario.</p>
            ) : (
              <div className="presentaciones-lista">
                {usuario.permisos.map((clave) => (
                  <span key={clave} className="etiqueta ambar">{NOMBRES_PERMISOS[clave] || clave}</span>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <section className="tarjeta" aria-labelledby="titulo-clave">
        <h3 id="titulo-clave">Cambiar contraseña</h3>
        <form onSubmit={guardar} noValidate>
          <CampoContrasena etiqueta="Contraseña actual" valor={actual} onCambiar={setActual} error={errores.actual} autoComplete="current-password" />
          <CampoContrasena etiqueta="Contraseña nueva" valor={nueva} onCambiar={setNueva} error={errores.nueva} ayuda={AYUDA_CONTRASENA} />
          <CampoContrasena etiqueta="Repite la contraseña nueva" valor={confirmacion} onCambiar={setConfirmacion} error={errores.confirmacion} />
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />} Actualizar contraseña
          </button>
        </form>
      </section>
    </div>
  );
}