// frontend/src/pages/usuarios/Usuarios.jsx
// Gestión de usuarios (solo administrador, validado por la ruta y por el
// backend): lista con búsqueda, alta, edición de datos, rol y permisos,
// restablecimiento de contraseña y activación o desactivación con
// confirmación. Un administrador no puede desactivarse a sí mismo.

import { useCallback, useEffect, useState } from 'react';
import { KeyRound, Pencil, Power, RefreshCw, Search, UserPlus, Users } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../../components/common/Confirmar.jsx';
import FormularioUsuario from '../../components/usuarios/FormularioUsuario.jsx';
import ModalRestablecer from '../../components/usuarios/ModalRestablecer.jsx';
import { mensajeDeError } from '../../services/api.js';
import { obtenerPerfilServicio } from '../../services/modules/authService.js';
import { actualizarUsuario, listarUsuarios } from '../../services/modules/usuariosService.js';
import { normalizar } from '../../utils/texto.js';
import '../../styles/catalogo.css';

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const [miId, setMiId] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [busqueda, setBusqueda] = useState('');

  const [formulario, setFormulario] = useState({ abierto: false, usuario: null });
  const [paraRestablecer, setParaRestablecer] = useState(null);
  const [paraDesactivar, setParaDesactivar] = useState(null);
  const [procesando, setProcesando] = useState(false);

  // Bloque: carga la lista; "silencioso" refresca sin mostrar el estado de carga
  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    try {
      setUsuarios(await listarUsuarios());
      setError('');
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
    // El id propio no está en la sesión guardada: se pide una vez para proteger la propia cuenta
    obtenerPerfilServicio().then((perfil) => setMiId(perfil.id)).catch(() => {});
  }, [cargar]);

  // Bloque: filtra por nombre, usuario o correo
  const texto = normalizar(busqueda.trim());
  const filtrados = usuarios.filter(
    (u) => !texto || [u.nombre_completo, u.nombre_usuario, u.correo].some((valor) => normalizar(valor).includes(texto))
  );

  // Bloque: activar es inmediato; desactivar pide confirmación porque cierra el acceso
  async function cambiarEstado(usuario, activo) {
    setProcesando(true);
    try {
      await actualizarUsuario(usuario.id, { activo });
      toast.success(activo ? `${usuario.nombre_usuario} activado.` : `${usuario.nombre_usuario} desactivado.`);
      cargar(true);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
      setParaDesactivar(null);
    }
  }

  return (
    <div className="catalogo">
      <div className="catalogo-barra">
        <div className="campo-caja">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Buscar por nombre, usuario o correo…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar usuario"
            maxLength={64}
          />
        </div>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => cargar()} aria-label="Actualizar usuarios">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        <button type="button" className="boton boton-primario boton-compacto" onClick={() => setFormulario({ abierto: true, usuario: null })}>
          <UserPlus size={18} aria-hidden="true" /> Nuevo usuario
        </button>
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="tarjeta">
          {Array.from({ length: 4 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 44, marginBottom: 10 }} />)}
        </div>
      ) : filtrados.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Users size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>{usuarios.length === 0 ? 'Aún no hay usuarios' : 'Sin resultados'}</h2>
          <p className="texto-suave">Prueba con otra búsqueda.</p>
        </section>
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla-datos">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Permisos</th>
                <th>Estado</th>
                <th><span className="solo-lectura">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((u) => {
                const esPropio = u.id === miId;
                return (
                  <tr key={u.id} className={u.activo ? '' : 'fila-inactiva'}>
                    <td>
                      <strong>{u.nombre_completo}</strong>
                      <div className="texto-suave">@{u.nombre_usuario}{esPropio && ' · tú'}</div>
                    </td>
                    <td data-label="Correo">{u.correo}</td>
                    <td data-label="Rol"><span className={`etiqueta ${u.rol === 'administrador' ? 'ambar' : 'gris'}`}>{u.rol === 'administrador' ? 'Administrador' : 'Empleado'}</span></td>
                    <td data-label="Permisos">
                      {u.rol === 'administrador' ? 'Acceso completo' : u.permisos.length ? `${u.permisos.length} adicional(es)` : 'Solo ventas e inventario'}
                    </td>
                    <td data-label="Estado"><span className={`etiqueta ${u.activo ? 'verde' : 'rojo'}`}>{u.activo ? 'Activo' : 'Inactivo'}</span></td>
                    <td className="celda-acciones">
                      <button type="button" className="boton-icono-borde" onClick={() => setFormulario({ abierto: true, usuario: u })} aria-label={`Editar a ${u.nombre_usuario}`}>
                        <Pencil size={16} />
                      </button>
                      <button type="button" className="boton-icono-borde" onClick={() => setParaRestablecer(u)} aria-label={`Restablecer la contraseña de ${u.nombre_usuario}`}>
                        <KeyRound size={16} />
                      </button>
                      {!esPropio && (
                        <button
                          type="button"
                          className={`boton-icono-borde ${u.activo ? 'peligro' : ''}`}
                          onClick={() => (u.activo ? setParaDesactivar(u) : cambiarEstado(u, true))}
                          aria-label={u.activo ? `Desactivar a ${u.nombre_usuario}` : `Activar a ${u.nombre_usuario}`}
                        >
                          <Power size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <FormularioUsuario
        abierto={formulario.abierto}
        usuario={formulario.usuario}
        esPropio={formulario.usuario?.id === miId}
        onCerrar={() => setFormulario({ abierto: false, usuario: null })}
        onGuardado={() => {
          setFormulario({ abierto: false, usuario: null });
          cargar(true);
        }}
      />
      <ModalRestablecer usuario={paraRestablecer} onCerrar={() => setParaRestablecer(null)} />
      <Confirmar
        abierto={Boolean(paraDesactivar)}
        titulo="Desactivar usuario"
        mensaje={`"${paraDesactivar?.nombre_completo ?? ''}" no podrá iniciar sesión hasta que lo actives de nuevo. Su historial de ventas se conserva.`}
        textoConfirmar="Desactivar"
        peligro
        cargando={procesando}
        onConfirmar={() => cambiarEstado(paraDesactivar, false)}
        onCancelar={() => setParaDesactivar(null)}
      />
    </div>
  );
}