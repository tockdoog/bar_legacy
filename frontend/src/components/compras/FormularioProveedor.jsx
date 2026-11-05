// frontend/src/components/compras/FormularioProveedor.jsx
// Ventana para crear o editar un proveedor: nombre, canal de pedido, teléfono y
// notas. Valida en el cliente las mismas reglas del backend.

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import Campo from '../forms/Campo.jsx';
import Modal from '../common/Modal.jsx';
import { mensajeDeError } from '../../services/api.js';
import { actualizarProveedor, crearProveedor } from '../../services/modules/proveedoresService.js';
import { CANALES } from '../../utils/proveedores.js';

const REGEX_TELEFONO = /^[0-9+()\s-]{0,30}$/;

export default function FormularioProveedor({ abierto, proveedor, onCerrar, onGuardado }) {
  const esEdicion = Boolean(proveedor);
  const [valores, setValores] = useState({ nombre: '', canal: 'otro', telefono: '', notas: '' });
  const [errores, setErrores] = useState({});
  const [guardando, setGuardando] = useState(false);

  // Bloque: reinicia el formulario cada vez que se abre
  useEffect(() => {
    if (!abierto) return;
    setValores({
      nombre: proveedor?.nombre ?? '',
      canal: proveedor?.canal ?? 'otro',
      telefono: proveedor?.telefono ?? '',
      notas: proveedor?.notas ?? '',
    });
    setErrores({});
    setGuardando(false);
  }, [abierto, proveedor]);

  const poner = (campo) => (evento) => setValores((previo) => ({ ...previo, [campo]: evento.target.value }));

  async function guardar(evento) {
    evento.preventDefault();
    const encontrados = {};
    if (valores.nombre.trim().length < 2) encontrados.nombre = 'Escribe al menos 2 caracteres.';
    if (!REGEX_TELEFONO.test(valores.telefono)) encontrados.telefono = 'Solo números, espacios, +, - y paréntesis.';
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) return;

    const carga = {
      nombre: valores.nombre.trim(),
      canal: valores.canal,
      telefono: valores.telefono.trim() || null,
      notas: valores.notas.trim() || null,
    };

    setGuardando(true);
    try {
      if (esEdicion) await actualizarProveedor(proveedor.id, carga);
      else await crearProveedor(carga);
      toast.success(esEdicion ? 'Proveedor actualizado.' : 'Proveedor creado.');
      onGuardado();
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo={esEdicion ? 'Editar proveedor' : 'Nuevo proveedor'} ancho={480} bloqueado={guardando}>
      <form onSubmit={guardar} noValidate>
        <Campo etiqueta="Nombre" error={errores.nombre}>
          <input type="text" value={valores.nombre} onChange={poner('nombre')} maxLength={120} autoFocus />
        </Campo>
        <Campo etiqueta="Canal de pedido">
          <select value={valores.canal} onChange={poner('canal')}>
            {CANALES.map((c) => <option key={c.valor} value={c.valor}>{c.etiqueta}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Teléfono (opcional)" error={errores.telefono}>
          <input type="tel" inputMode="tel" value={valores.telefono} onChange={poner('telefono')} maxLength={30} />
        </Campo>
        <Campo etiqueta="Notas (opcional)">
          <textarea value={valores.notas} onChange={poner('notas')} maxLength={255} rows={3} />
        </Campo>
        <div className="modal-acciones">
          <button type="button" className="boton boton-secundario" onClick={onCerrar} disabled={guardando}>Cancelar</button>
          <button type="submit" className="boton boton-primario" disabled={guardando}>
            {guardando && <Loader2 size={18} className="girar" aria-hidden="true" />} Guardar
          </button>
        </div>
      </form>
    </Modal>
  );
}