// frontend/src/pages/promociones/Promociones.jsx
// Gestión de promociones (combos). Todos los usuarios las consultan en tarjetas;
// el administrador además crea, edita, activa y desactiva (el backend valida el
// rol) y puede ver las inactivas. Los costos y la ganancia solo se ven con rol
// de administrador. El backend no maneja fechas de vigencia.

import { useCallback, useEffect, useState } from 'react';
import { Percent, Plus, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import Confirmar from '../../components/common/Confirmar.jsx';
import FormularioPromocion from '../../components/promociones/FormularioPromocion.jsx';
import TarjetaPromocionGestion from '../../components/promociones/TarjetaPromocionGestion.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { mensajeDeError } from '../../services/api.js';
import { listarProductos } from '../../services/modules/catalogoService.js';
import { actualizarPromocion, listarPromocionesGestion } from '../../services/modules/promocionesService.js';
import '../../styles/catalogo.css';
import '../../styles/compras.css';

export default function Promociones() {
  const { esAdmin } = useAuth();
  const [promociones, setPromociones] = useState([]);
  const [productos, setProductos] = useState([]);
  const [verTodas, setVerTodas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const [formulario, setFormulario] = useState({ abierto: false, promocion: null });
  const [porDesactivar, setPorDesactivar] = useState(null);
  const [procesando, setProcesando] = useState(false);

  // Bloque: carga promociones (con inactivas si el administrador lo pide) y, para el administrador, los productos
  const cargar = useCallback(
    async (silencioso = false) => {
      if (!silencioso) setCargando(true);
      const [resPromos, resProductos] = await Promise.allSettled([
        listarPromocionesGestion(esAdmin && verTodas),
        esAdmin ? listarProductos() : Promise.resolve([]),
      ]);
      if (resPromos.status === 'fulfilled') {
        setPromociones(resPromos.value);
        setError('');
      } else {
        setError(mensajeDeError(resPromos.reason));
      }
      if (resProductos.status === 'fulfilled') setProductos(resProductos.value);
      setCargando(false);
    },
    [esAdmin, verTodas]
  );

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Bloque: activar es inmediato; desactivar pide confirmación porque deja de aparecer en el POS
  async function cambiarEstado(promocion, activa) {
    setProcesando(true);
    try {
      await actualizarPromocion(promocion.id, { activa });
      toast.success(activa ? `"${promocion.nombre}" activada.` : `"${promocion.nombre}" desactivada.`);
      cargar(true);
    } catch (fallo) {
      toast.error(mensajeDeError(fallo));
    } finally {
      setProcesando(false);
      setPorDesactivar(null);
    }
  }

  const alAlternar = (promocion) => (promocion.activa ? setPorDesactivar(promocion) : cambiarEstado(promocion, true));

  return (
    <div className="catalogo">
      <div className="catalogo-barra">
        <h2 className="titulo-seccion">Promociones</h2>
        {esAdmin && (
          <div className="selector-periodo" role="group" aria-label="Qué promociones mostrar">
            <button type="button" className={!verTodas ? 'activo' : ''} onClick={() => setVerTodas(false)}>Activas</button>
            <button type="button" className={verTodas ? 'activo' : ''} onClick={() => setVerTodas(true)}>Todas</button>
          </div>
        )}
        <button type="button" className="boton boton-secundario boton-compacto" onClick={() => cargar()} aria-label="Actualizar promociones">
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
        </button>
        {esAdmin && (
          <button type="button" className="boton boton-primario boton-compacto" onClick={() => setFormulario({ abierto: true, promocion: null })}>
            <Plus size={18} aria-hidden="true" /> Nueva promoción
          </button>
        )}
      </div>

      {error && <p className="mensaje-error" role="alert">{error}</p>}

      {cargando ? (
        <div className="promos-rejilla">
          {Array.from({ length: 3 }, (_, i) => <div key={i} className="esqueleto" style={{ height: 260 }} />)}
        </div>
      ) : promociones.length === 0 ? (
        <section className="tarjeta estado-vacio">
          <Percent size={40} color="var(--dorado-oscuro)" aria-hidden="true" />
          <h2>No hay promociones {verTodas ? '' : 'activas'}</h2>
          <p className="texto-suave">
            {esAdmin ? 'Crea un combo con el botón "Nueva promoción".' : 'Cuando el administrador cree promociones aparecerán aquí.'}
          </p>
        </section>
      ) : (
        <div className="promos-rejilla">
          {promociones.map((p) => (
            <TarjetaPromocionGestion
              key={p.id}
              promocion={p}
              esAdmin={esAdmin}
              onEditar={(promo) => setFormulario({ abierto: true, promocion: promo })}
              onAlternar={alAlternar}
            />
          ))}
        </div>
      )}

      {esAdmin && (
        <FormularioPromocion
          abierto={formulario.abierto}
          promocion={formulario.promocion}
          productos={productos}
          onCerrar={() => setFormulario({ abierto: false, promocion: null })}
          onGuardado={() => {
            setFormulario({ abierto: false, promocion: null });
            cargar(true);
          }}
        />
      )}
      <Confirmar
        abierto={Boolean(porDesactivar)}
        titulo="Desactivar promoción"
        mensaje={`"${porDesactivar?.nombre ?? ''}" dejará de aparecer en el punto de venta. Podrás activarla de nuevo cuando quieras.`}
        textoConfirmar="Desactivar"
        peligro
        cargando={procesando}
        onConfirmar={() => cambiarEstado(porDesactivar, false)}
        onCancelar={() => setPorDesactivar(null)}
      />
    </div>
  );
}