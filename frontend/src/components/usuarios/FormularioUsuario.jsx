// frontend/src/components/usuarios/FormularioUsuario.jsx
// Ventana para crear o editar un usuario. Valida en el cliente las mismas
// reglas del backend. Los permisos granulares se piden al backend (catálogo
// único) y solo aplican a empleados: un administrador ya tiene acceso completo.
// Al crear se define la contraseña; para cambiarla después se usa el
// restablecimiento. El nombre de usuario no se puede editar.

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import Campo from '../forms/Campo.jsx';
import CampoContrasena from '../forms/CampoContrasena.jsx';
import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import {
  actualizarUsuario,
  crearUsuario,
  listarPermisosDisponibles,
} from '../../services/modules/usuariosService.js';
import { AYUDA_CONTRASENA, validarContrasena } from '../../utils/contrasena.js';

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function valoresIniciales(usuario) {
  return {
    nombre_completo: usuario?.nombre_completo ?? '',
    nombre_usuario: usuario?.nombre_usuario ?? '',
    correo: usuario?.correo ?? '',
    rol: usuario?.rol ?? 'empleado',
    contrasena: '',
    permisos: usuario?.permisos ?? [],
  };
}

export default function FormularioUsuario({ abierto, usuario, esPropio, onCerrar, onGuardado }) {
  const esEdicion = Boolean(usuario);
  const [valores, setValores] = useState(valoresIniciales(null));
  const [errores, setErrores] = useState({});
  const [catalogo, setCatalogo] = useState([]);
  const [guardando, setGuardando] = useState(false);

  // Bloque: reinicia el formulario cada vez que se abre
  useEffect(() => {
    if (!abierto) return;
    setValores(valoresIniciales(usuario));
    setErrores({});
    setGuardando(false);
  }, [abierto, usuario]);

  // Bloque: trae el catálogo de permisos desde el backend (única fuente de verdad)
  useEffect(() => {
    if (!abierto) return;
    listarPermisosDisponibles()
      .then(setCatalogo)
      .catch((fallo) => toast.error(mensajeDeError(fallo)));
  }, [abierto]);

  const poner = (campo) => (evento) => setValores((previo) => ({ ...previo, [campo]: evento.target.value }));

  const alternarPermiso = (clave) =>
    setValores((previo) => ({
      ...previo,
      permisos: previo.permisos.includes(clave)
        ? previo.permisos.filter((p) => p !== clave)
        : [...previo.permisos, clave],
    }));

  // Bloque: valida, y crea o actualiza
  async function guardar(evento) {
    evento.preventDefault();
    const e = {};
    const nombre = valores.nombre_completo.trim();
    const usuarioTexto = valores.nombre_usuario.trim();
    if (nombre.length < 3 || nombre.length > 120) e.nombre_completo = 'Entre 3 y 120 caracteres.';
    if (!esEdicion && (usuarioTexto.length < 3 || usuarioTexto.length > 50)) e.nombre_usuario = 'Entre 3 y 50 caracteres.';
    if (!REGEX_CORREO.test(valores.correo.trim())) e.correo = 'Escribe un correo válido.';
    if (!esEdicion) {
      const problema = validarContrasena(valores.contrasena);
      if (problema) e.contrasena = problema;
    }
    setErrores(e);
    if (Object.keys(e).length > 0) return;

    const esEmpleado = valores.rol === 'empleado';
    setGuardando(true);
    try {
      if (esEdicion) {
        await actualizarUsuario(usuario.id, {
          nombre_completo: nombre,
          correo: valores.correo.trim(),
          rol: valores.rol,
          ...(esEmpleado ? { permisos: valores.permisos } : {}),
        });
      } else {
        await crearUsuario({
          nombre_completo: nombre,
          nombre_usuario: usuarioTexto,
          correo: valores.correo.trim(),
          contrasena: valores.contrasena,
          rol: valores.rol,
          permisos: esEmpleado ? valores.permisos : [],
        });
      }
      toast.success(esEdicion ? 'Usuario actualizado.' : 'Usuario creado.');
      onGuardado();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={esEdicion ? 'Editar usuario' : 'Nuevo usuario'} ancho={640} bloqueado={guardando}>
      <form onSubmit={guardar} noValidate>
        <div className="formulario-rejilla">
          <Campo etiqueta="Nombre completo" error={errores.nombre_completo} className="ocupa-todo">
            <input type="text" value={valores.nombre_completo} onChange={poner('nombre_completo')} maxLength={120} autoFocus />
          </Campo>
          <Campo etiqueta="Nombre de usuario" error={errores.nombre_usuario} ayuda={esEdicion ? 'No se puede cambiar.' : 'Con este nombre inicia sesión.'}>
            <input type="text" value={valores.nombre_usuario} onChange={poner('nombre_usuario')} maxLength={50} autoCapitalize="none" autoComplete="off" disabled={esEdicion} />
          </Campo>
          <Campo etiqueta="Correo" error={errores.correo}>
            <input type="email" value={valores.correo} onChange={poner('correo')} maxLength={120} autoComplete="off" />
          </Campo>
          <Campo etiqueta="Rol" ayuda={esPropio ? 'No puedes cambiar tu propio rol.' : undefined}>
            <select value={valores.rol} onChange={poner('rol')} disabled={esPropio}>
              <option value="empleado">Empleado</option>
              <option value="administrador">Administrador</option>
            </select>
          </Campo>
          {!esEdicion && (
            <CampoContrasena
              etiqueta="Contraseña inicial"
              valor={valores.contrasena}
              onCambiar={(v) => setValores((previo) => ({ ...previo, contrasena: v }))}
              error={errores.contrasena}
              ayuda={AYUDA_CONTRASENA}
            />
          )}
        </div>

        {/* Permisos granulares: solo para empleados */}
        <div className="seccion-form">
          <h3 className="subtitulo-form">Permisos</h3>
          {valores.rol === 'administrador' ? (
            <p className="texto-suave">El administrador tiene acceso completo al sistema.</p>
          ) : (
            <>
              <p className="texto-suave">Un empleado siempre puede vender y consultar el inventario. Marca lo adicional que podrá hacer:</p>
              <div className="permisos-lista">
                {catalogo.map((permiso) => (
                  <label key={permiso.clave} className="casilla">
                    <input type="checkbox" checked={valores.permisos.includes(permiso.clave)} onChange={() => alternarPermiso(permiso.clave)} />
                    <span>{permiso.descripcion}</span>
                  </label>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="modal-acciones">
          <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />}
            {esEdicion ? 'Guardar cambios' : 'Crear usuario'}
          </button>
        </div>
      </form>
    </Modal>
  );
}