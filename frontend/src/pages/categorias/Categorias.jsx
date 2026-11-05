// frontend/src/pages/categorias/Categorias.jsx
// Categorías y presentaciones. Las categorías se pueden crear, editar y eliminar
// (solo administrador, el backend lo valida). Las presentaciones son un texto
// libre de cada producto, sin endpoint propio: aquí se listan como consulta y
// se editan al editar el producto.

import { useState } from 'react';
import { Loader2, Package, Pencil, Plus, Tags, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../../components/common/Confirmar.jsx';
import Modal from '../../components/common/Modal.jsx';
import Campo from '../../components/forms/Campo.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import useCatalogo from '../../hooks/useCatalogo.js';
import { mensajeDeError } from '../../services/api.js';
import {
  actualizarCategoria,
  crearCategoria,
  eliminarCategoria,
} from '../../services/modules/categoriasService.js';
import '../../styles/catalogo.css';

export default function Categorias() {
  const { esAdmin } = useAuth();
  const { productos, categorias, presentaciones, cargando, error, recargar } = useCatalogo();

  const [edicion, setEdicion] = useState({ abierto: false, categoria: null });
  const [nombre, setNombre] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [errorNombre, setErrorNombre] = useState('');
  const [porEliminar, setPorEliminar] = useState(null);
  const [procesando, setProcesando] = useState(false);

  // Bloque: cantidad de productos activos por categoría
  const conteo = {};
  productos.forEach((p) => {
    if (p.categoria_id) conteo[p.categoria_id] = (conteo[p.categoria_id] || 0) + 1;
  });

  // Bloque: abre el formulario para crear (sin categoría) o editar
  function abrirFormulario(categoria = null) {
    setNombre(categoria?.nombre ?? '');
    setDescripcion(categoria?.descripcion ?? '');
    setErrorNombre('');
    setEdicion({ abierto: true, categoria });
  }
  const cerrarFormulario = () => setEdicion({ abierto: false, categoria: null });

  async function guardar(evento) {
    evento.preventDefault();
    const nombreLimpio = nombre.trim();
    if (nombreLimpio.length < 2) {
      setErrorNombre('Escribe al menos 2 caracteres.');
      return;
    }
    const carga = { nombre: nombreLimpio, descripcion: descripcion.trim() || null };

    setProcesando(true);
    try {
      if (edicion.categoria) await actualizarCategoria(edicion.categoria.id, carga);
      else await crearCategoria(carga);
      toast.success(edicion.categoria ? 'Categoría actualizada.' : 'Categoría creada.');
      cerrarFormulario();
      recargar(true);
    } catch (fallo) {
      setErrorNombre(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
    }
  }

  async function confirmarEliminacion() {
    setProcesando(true);
    try {
      await eliminarCategoria(porEliminar.id);
      toast.success(`Categoría "${porEliminar.nombre}" eliminada.`);
      recargar(true);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
      setPorEliminar(null);
    }
  }

  return (
    <div className="catalogo">
      <div className="catalogo-barra">
        <h2 className="titulo-seccion">Categorías</h2>
        {esAdmin && (
          <button type="button" className="boton boton-primario boton-compacto" onClick={() => abrirFormulario()}>
            <Plus size={18} aria-hidden="true" /> Nueva categoría
          </button>
        )}
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="categorias-rejilla">
          {Array.from({ length: 4 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 110 }} />)}
        </div>
      ) : categorias.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Tags size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>Aún no hay categorías</h2>
          <p className="texto-suave">
            {esAdmin ? 'Crea la primera con el botón "Nueva categoría".' : 'Pídele al administrador que las cree.'}
          </p>
        </section>
      ) : (
        <div className="categorias-rejilla">
          {categorias.map((c) => (
            <article key={c.id} className="tarjeta categoria-tarjeta">
              <div>
                <h3>{c.nombre}</h3>
                <p className="texto-suave">{c.descripcion || 'Sin descripción'}</p>
              </div>
              <div className="categoria-pie">
                <span className="etiqueta ambar"><Package size={12} aria-hidden="true" /> {conteo[c.id] || 0} producto(s)</span>
                {esAdmin && (
                  <span className="celda-acciones">
                    <button type="button" className="boton-icono-borde" onClick={() => abrirFormulario(c)} aria-label={`Editar ${c.nombre}`}>
                      <Pencil size={16} />
                    </button>
                    <button type="button" className="boton-icono-borde peligro" onClick={() => setPorEliminar(c)} aria-label={`Eliminar ${c.nombre}`}>
                      <Trash2 size={16} />
                    </button>
                  </span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Presentaciones: solo consulta, se editan en cada producto */}
      <section className="tarjeta" aria-labelledby="titulo-presentaciones">
        <h3 id="titulo-presentaciones">Presentaciones en uso</h3>
        <p className="texto-suave">
          La presentación es un dato libre de cada producto (por ejemplo: unidad, paquete o caja). Para cambiarla, edita el producto.
        </p>
        {presentaciones.length === 0 ? (
          <p className="texto-suave">Todavía no hay productos con presentación registrada.</p>
        ) : (
          <div className="presentaciones-lista">
            {presentaciones.map((p) => (
              <span key={p.nombre} className="etiqueta gris">{p.nombre} · {p.cantidad}</span>
            ))}
          </div>
        )}
      </section>

      {/* Ventanas */}
      <Modal abierto={edicion.abierto} onCerrar={cerrarFormulario} titulo={edicion.categoria ? 'Editar categoría' : 'Nueva categoría'} ancho={440} bloqueado={procesando}>
        <form onSubmit={guardar} noValidate>
          <Campo etiqueta="Nombre" error={errorNombre}>
            <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={80} autoFocus />
          </Campo>
          <Campo etiqueta="Descripción (opcional)">
            <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={255} rows={3} />
          </Campo>
          <div className="modal-acciones">
            <button type="button" className="boton boton-secundario" onClick={cerrarFormulario} disabled={procesando}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={procesando}>
              {procesando && <Loader2 size={18} className="girar" aria-hidden="true" />} Guardar
            </button>
          </div>
        </form>
      </Modal>
      <Confirmar
        abierto={Boolean(porEliminar)}
        titulo="Eliminar categoría"
        mensaje={`¿Eliminar la categoría "${porEliminar?.nombre ?? ''}"? Solo es posible si ningún producto la está usando.`}
        textoConfirmar="Eliminar"
        peligro
        cargando={procesando}
        onConfirmar={confirmarEliminacion}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}