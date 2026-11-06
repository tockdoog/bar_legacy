// frontend/src/pages/test/Diagnostico.jsx
// Ruta de pruebas (/test): verifica de punta a punta que el frontend está bien
// conectado al backend: URL configurada, mixed content, CORS, zona horaria, salud
// de la API, suscripción, logo y, si hay sesión, los endpoints principales según el
// rol. Es pública para poder usarla antes de iniciar sesión. No muestra secretos.
// Ocúltala con VITE_HABILITAR_TEST=false cuando termines las pruebas.
//
// CAMBIOS: la prueba de salud se ejecuta primero y el resto después. En Vercel, la
// primera petición tras un rato sin uso crea las tablas (arranque en frío); lanzar 12
// peticiones a la vez en ese momento hacía fallar varias con un 503. También se
// protege la lectura de permisos cuando el perfil no los trae.

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Loader2, MinusCircle, PlayCircle, XCircle } from 'lucide-react';

import api, { mensajeDeError, urlApi } from '../../services/api.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { horaActualBogota, hoyBogota } from '../../utils/formato.js';
import '../../styles/diagnostico.css';

// Pruebas que deben terminar antes de lanzar las demás (despiertan el servidor y la base de datos)
const PRUEBAS_PRIMERO = ['salud'];

// Bloque: crea una prueba que consulta un endpoint GET; un 403 se reporta como alerta (rol sin permiso)
const consultar = (ruta, describir, params) => async () => {
  try {
    const { data } = await api.get(ruta, { params });
    return { estado: 'ok', detalle: describir(data) };
  } catch (error) {
    if (error.response?.status === 403) {
      return { estado: 'alerta', detalle: 'Sin permiso con tu rol (puede ser normal).' };
    }
    throw error;
  }
};

// Bloque: comprueba que el logo servido por el backend carga como imagen
const probarLogo = () =>
  new Promise((resolver) => {
    const imagen = new Image();
    const limite = setTimeout(() => resolver({ estado: 'alerta', detalle: 'El logo tardó demasiado en cargar.' }), 8000);
    imagen.onload = () => {
      clearTimeout(limite);
      resolver({ estado: 'ok', detalle: `${urlApi}/imagenes/logo.png` });
    };
    imagen.onerror = () => {
      clearTimeout(limite);
      resolver({ estado: 'alerta', detalle: 'No se pudo cargar /imagenes/logo.png (revisa que exista en el backend).' });
    };
    imagen.src = `${urlApi}/imagenes/logo.png`;
  });

// Bloque: lista de pruebas; "sesion" exige haber iniciado sesión, "permiso" un permiso granular
const hoy = () => hoyBogota();
const PRUEBAS = [
  {
    id: 'entorno',
    nombre: 'Configuración del frontend',
    ejecutar: async () => {
      const paginaSegura = window.location.protocol === 'https:';
      const apiInsegura = urlApi.startsWith('http:') && !urlApi.includes('localhost') && !urlApi.includes('127.0.0.1');
      if (paginaSegura && apiInsegura) {
        return { estado: 'error', detalle: `La página usa HTTPS pero la API es HTTP (${urlApi}). El navegador la bloqueará.` };
      }
      return { estado: 'ok', detalle: `API: ${urlApi} · modo: ${import.meta.env.MODE}` };
    },
  },
  {
    id: 'hora',
    nombre: 'Zona horaria (Bogotá)',
    ejecutar: async () => ({
      estado: 'ok',
      detalle: `Hora en Bogotá: ${horaActualBogota()} · zona del dispositivo: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`,
    }),
  },
  {
    id: 'salud',
    nombre: 'Conexión con la API (/api/salud)',
    ejecutar: async () => {
      const { data } = await api.get('/api/salud');
      return data?.estado === 'ok'
        ? { estado: 'ok', detalle: 'La API responde correctamente (CORS correcto).' }
        : { estado: 'error', detalle: 'Respuesta inesperada de la API.' };
    },
  },
  {
    id: 'suscripcion',
    nombre: 'Estado de la suscripción',
    ejecutar: consultar('/api/suscripcion/estado', (d) =>
      d.bloqueado ? 'Sistema BLOQUEADO por falta de pago.' : `Activa. Días restantes: ${d.dias_restantes}.`
    ),
  },
  { id: 'logo', nombre: 'Logo servido por el backend', ejecutar: probarLogo },
  {
    id: 'perfil',
    nombre: 'Sesión y perfil (/api/auth/yo)',
    sesion: true,
    ejecutar: consultar(
      '/api/auth/yo',
      (d) => `${d.nombre_completo} · rol ${d.rol} · ${(d.permisos || []).length} permiso(s)`
    ),
  },
  {
    id: 'productos',
    nombre: 'Productos',
    sesion: true,
    ejecutar: consultar('/api/productos/', (d) => `${d.length} producto(s) activo(s).`),
  },
  {
    id: 'categorias',
    nombre: 'Categorías',
    sesion: true,
    ejecutar: consultar('/api/categorias/', (d) => `${d.length} categoría(s).`),
  },
  {
    id: 'mesas',
    nombre: 'Mesas',
    sesion: true,
    ejecutar: consultar('/api/mesas/', (d) => `${d.length} mesa(s).`),
  },
  {
    id: 'promociones',
    nombre: 'Promociones',
    sesion: true,
    ejecutar: consultar('/api/promociones/', (d) => `${d.length} promoción(es) activa(s).`),
  },
  {
    id: 'abiertas',
    nombre: 'Ventas abiertas',
    sesion: true,
    ejecutar: consultar('/api/ventas/abiertas', (d) => `${d.length} venta(s) abierta(s).`),
  },
  {
    id: 'reportes',
    nombre: 'Reportes (ventas de hoy)',
    sesion: true,
    permiso: 'reportes_ver',
    ejecutar: async () =>
      consultar('/api/reportes/ventas', (d) => `${d.resumen?.['Numero de ventas'] ?? 0} venta(s) hoy.`, {
        fecha_inicio: hoy(),
        fecha_fin: hoy(),
      })(),
  },
  {
    id: 'finanzas',
    nombre: 'Configuración financiera',
    sesion: true,
    permiso: 'finanzas_gestionar',
    ejecutar: consultar('/api/finanzas/configuracion', (d) => `${d.etiqueta_impuesto} · ${d.porcentaje_impuesto} %`),
  },
];

// Bloque: icono según el estado de cada prueba
const ICONOS = {
  ok: <CheckCircle2 size={20} color="var(--verde)" aria-label="Correcta" />,
  alerta: <AlertTriangle size={20} color="var(--dorado-oscuro)" aria-label="Advertencia" />,
  error: <XCircle size={20} color="var(--rojo)" aria-label="Fallida" />,
  omitida: <MinusCircle size={20} color="var(--texto-suave)" aria-label="Omitida" />,
  cargando: <Loader2 size={20} className="girar" aria-label="Ejecutando" />,
};

export default function Diagnostico() {
  const { autenticado, tienePermiso } = useAuth();
  const [resultados, setResultados] = useState({});
  const [ejecutando, setEjecutando] = useState(false);

  // Bloque: ejecuta una prueba y guarda su resultado con el tiempo que tardó
  const ejecutarPrueba = useCallback(async (prueba) => {
    const inicio = performance.now();
    let resultado;
    try {
      resultado = await prueba.ejecutar();
    } catch (error) {
      resultado = { estado: 'error', detalle: mensajeDeError(error) };
    }
    const ms = Math.round(performance.now() - inicio);
    setResultados((previo) => ({ ...previo, [prueba.id]: { ...resultado, ms } }));
  }, []);

  // Bloque: omite las pruebas que no aplican y ejecuta el resto: primero la salud, luego las demás en paralelo
  const ejecutarTodo = useCallback(async () => {
    setEjecutando(true);
    const inicial = {};
    PRUEBAS.forEach((prueba) => {
      if (prueba.sesion && !autenticado) {
        inicial[prueba.id] = { estado: 'omitida', detalle: 'Inicia sesión para ejecutar esta prueba.' };
      } else if (prueba.permiso && !tienePermiso(prueba.permiso)) {
        inicial[prueba.id] = { estado: 'omitida', detalle: `Requiere el permiso "${prueba.permiso}".` };
      } else {
        inicial[prueba.id] = { estado: 'cargando', detalle: 'Ejecutando…' };
      }
    });
    setResultados(inicial);

    const pendientes = PRUEBAS.filter((prueba) => inicial[prueba.id].estado === 'cargando');
    await Promise.all(pendientes.filter((p) => PRUEBAS_PRIMERO.includes(p.id)).map(ejecutarPrueba));
    await Promise.all(pendientes.filter((p) => !PRUEBAS_PRIMERO.includes(p.id)).map(ejecutarPrueba));
    setEjecutando(false);
  }, [autenticado, tienePermiso, ejecutarPrueba]);

  useEffect(() => {
    ejecutarTodo();
  }, [ejecutarTodo]);

  // Bloque: resumen de la ejecución
  const lista = Object.values(resultados);
  const cuenta = (estado) => lista.filter((r) => r.estado === estado).length;

  return (
    <main className="diag-pagina">
      <section className="tarjeta diag-tarjeta">
        <h1 className="titulo-marca">Diagnóstico <span>del sistema</span></h1>
        <hr className="divisor-dorado" />
        <p className="texto-suave">
          Comprueba que el frontend se conecta bien con el backend. {autenticado ? 'Sesión activa.' : 'Sin sesión: las pruebas privadas se omiten.'}
        </p>

        <div className="diag-resumen" aria-live="polite">
          <span className="etiqueta verde">{cuenta('ok')} correctas</span>
          <span className="etiqueta ambar">{cuenta('alerta')} advertencias</span>
          <span className="etiqueta rojo">{cuenta('error')} fallidas</span>
          <span className="etiqueta gris">{cuenta('omitida')} omitidas</span>
        </div>

        <ul className="diag-lista">
          {PRUEBAS.map((prueba) => {
            const resultado = resultados[prueba.id];
            return (
              <li key={prueba.id} className="diag-fila">
                <span className="diag-icono">{ICONOS[resultado?.estado || 'cargando']}</span>
                <div className="diag-texto">
                  <strong>{prueba.nombre}</strong>
                  <span className="texto-suave">{resultado?.detalle || 'Pendiente…'}</span>
                </div>
                {resultado?.ms !== undefined && <span className="diag-ms">{resultado.ms} ms</span>}
              </li>
            );
          })}
        </ul>

        <div className="diag-acciones">
          <button type="button" className="boton boton-primario" onClick={ejecutarTodo} disabled={ejecutando}>
            {ejecutando ? <Loader2 className="girar" size={18} /> : <PlayCircle size={18} />}
            Ejecutar de nuevo
          </button>
          <Link to={autenticado ? '/' : '/login'} className="boton boton-secundario">
            {autenticado ? 'Ir al Dashboard' : 'Iniciar sesión'}
          </Link>
        </div>
      </section>
    </main>
  );
}