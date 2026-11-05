// frontend/src/pages/dashboard/Inicio.jsx
// Dashboard principal. Usa solo datos reales del backend: ventas de hoy, 7 y 30
// días con comparación frente al periodo anterior, ganancia estimada, productos
// más vendidos, actividad reciente, estado de mesas, cuentas abiertas y
// alertas de inventario. Los datos de reportes solo se piden si el usuario
// tiene el permiso "reportes_ver"; el resto de tarjetas funciona para todos.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Armchair,
  ArrowRight,
  Banknote,
  PackageX,
  Receipt,
  RefreshCw,
  ShoppingCart,
  TrendingUp,
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext.jsx';
import { MODULOS, puedeVerModulo } from '../../routes/navegacion.js';
import { mensajeDeError } from '../../services/api.js';
import {
  obtenerInventarioBajo,
  obtenerMesas,
  obtenerReporte,
  obtenerVentasAbiertas,
} from '../../services/modules/dashboardService.js';
import { formatearCOP, formatearFecha, formatearNumero, hoyBogota } from '../../utils/formato.js';
import {
  contarFilas,
  restarDias,
  serieDiaria,
  sumarCampo,
  variacionPorcentual,
} from '../../utils/indicadores.js';
import TarjetaEstadistica from '../../components/common/TarjetaEstadistica.jsx';
import GraficaBarras from '../../components/common/GraficaBarras.jsx';
import '../../styles/dashboard.css';

// Bloque: animación escalonada de aparición de las tarjetas
const contenedor = { oculto: {}, visible: { transition: { staggerChildren: 0.06 } } };
const elemento = { oculto: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0 } };

export default function Inicio() {
  const { usuario, esAdmin, tienePermiso } = useAuth();
  const verReportes = tienePermiso('reportes_ver');

  const [datos, setDatos] = useState({});
  const [errores, setErrores] = useState({});
  const [cargando, setCargando] = useState(true);
  const [diasGrafica, setDiasGrafica] = useState(14);

  // Bloque: carga en paralelo todos los datos; si una consulta falla, las demás siguen
  const cargarTodo = useCallback(async () => {
    setCargando(true);
    const hoy = hoyBogota();
    const inicio = restarDias(hoy, 29);

    const tareas = {
      inventarioBajo: obtenerInventarioBajo(),
      mesas: obtenerMesas(),
      abiertas: obtenerVentasAbiertas(),
    };
    if (verReportes) {
      tareas.ganancias = obtenerReporte('ganancias', inicio, hoy);
      tareas.ventas = obtenerReporte('ventas', inicio, hoy);
      tareas.masVendidos = obtenerReporte('mas-vendidos', inicio, hoy);
    }

    const claves = Object.keys(tareas);
    const resultados = await Promise.allSettled(Object.values(tareas));
    const nuevosDatos = {};
    const nuevosErrores = {};
    resultados.forEach((resultado, indice) => {
      if (resultado.status === 'fulfilled') nuevosDatos[claves[indice]] = resultado.value;
      else nuevosErrores[claves[indice]] = mensajeDeError(resultado.reason);
    });
    setDatos(nuevosDatos);
    setErrores(nuevosErrores);
    setCargando(false);
  }, [verReportes]);

  useEffect(() => {
    cargarTodo();
  }, [cargarTodo]);

  // Bloque: indicadores de ventas calculados a partir de los reportes
  const indicadores = useMemo(() => {
    const filasGanancias = datos.ganancias?.filas;
    const filasVentas = datos.ventas?.filas;
    if (!filasGanancias || !filasVentas) return null;

    const hoy = hoyBogota();
    const ayer = restarDias(hoy, 1);
    const sieteInicio = restarDias(hoy, 6);
    const sieteAntesInicio = restarDias(hoy, 13);
    const sieteAntesFin = restarDias(hoy, 7);
    const treintaInicio = restarDias(hoy, 29);

    const ventasHoy = sumarCampo(filasGanancias, 'Ventas', hoy, hoy);
    const ventasAyer = sumarCampo(filasGanancias, 'Ventas', ayer, ayer);
    const ventasSiete = sumarCampo(filasGanancias, 'Ventas', sieteInicio, hoy);
    const ventasSieteAntes = sumarCampo(filasGanancias, 'Ventas', sieteAntesInicio, sieteAntesFin);

    return {
      ventasHoy,
      variacionHoy: variacionPorcentual(ventasHoy, ventasAyer),
      cantidadHoy: contarFilas(filasVentas, hoy, hoy),
      ventasSiete,
      variacionSiete: variacionPorcentual(ventasSiete, ventasSieteAntes),
      cantidadSiete: contarFilas(filasVentas, sieteInicio, hoy),
      ventasTreinta: sumarCampo(filasGanancias, 'Ventas', treintaInicio, hoy),
      cantidadTreinta: contarFilas(filasVentas, treintaInicio, hoy),
      gananciaTreinta: sumarCampo(filasGanancias, 'Ganancia', treintaInicio, hoy),
      gananciaSiete: sumarCampo(filasGanancias, 'Ganancia', sieteInicio, hoy),
    };
  }, [datos.ganancias, datos.ventas]);

  // Bloque: serie para la gráfica según el periodo elegido (7, 14 o 30 días)
  const serie = useMemo(
    () => (datos.ganancias ? serieDiaria(datos.ganancias.filas, 'Ventas', hoyBogota(), diasGrafica) : []),
    [datos.ganancias, diasGrafica]
  );
  const serieConVentas = serie.some((punto) => punto.valor > 0);

  // Bloque: conteos de mesas
  const mesas = datos.mesas || [];
  const mesasOcupadas = mesas.filter((m) => m.estado === 'ocupada').length;
  const mesasPendientes = mesas.filter((m) => m.estado === 'pendiente_pago').length;
  const inventarioBajo = datos.inventarioBajo || [];
  const cuentasAbiertas = datos.abiertas?.length ?? 0;

  // Bloque: alertas importantes derivadas de los datos reales
  const alertas = [];
  if (inventarioBajo.length > 0) {
    alertas.push(`${inventarioBajo.length} producto(s) con inventario bajo o agotado.`);
  }
  if (mesasPendientes > 0) {
    alertas.push(`${mesasPendientes} mesa(s) pendiente(s) de pago.`);
  }

  // Bloque: productos más vendidos (los 5 primeros) y actividad reciente (últimas 6 ventas)
  const masVendidos = (datos.masVendidos?.filas || []).slice(0, 5);
  const maximoVendido = Math.max(...masVendidos.map((p) => p['Cantidad vendida']), 1);
  const actividad = [...(datos.ventas?.filas || [])].reverse().slice(0, 6);

  // Bloque: accesos rápidos según los permisos del usuario
  const accesos = ['/pos', '/mesas', '/inventario', '/compras']
    .map((ruta) => MODULOS.find((m) => m.ruta === ruta))
    .filter((m) => m && puedeVerModulo(m, { esAdmin, tienePermiso }));

  return (
    <motion.div className="dash" variants={contenedor} initial="oculto" animate="visible">
      {/* Saludo y botón de actualizar */}
      <motion.div className="dash-saludo" variants={elemento}>
        <div>
          <h2 className="titulo-marca">Hola, {usuario.nombre_completo.split(' ')[0]}</h2>
          <p className="texto-suave">Resumen del negocio en tiempo real.</p>
        </div>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={cargarTodo} disabled={cargando}>
          <RefreshCw size={18} className={cargando ? 'girar' : ''} aria-hidden="true" />
          Actualizar
        </button>
      </motion.div>

      {/* Alertas importantes */}
      {alertas.length > 0 && (
        <motion.div className="dash-alertas" variants={elemento} role="status">
          {alertas.map((texto) => (
            <p key={texto}><AlertTriangle size={16} aria-hidden="true" /> {texto}</p>
          ))}
        </motion.div>
      )}

      {/* Tarjetas de indicadores */}
      <motion.div className="dash-estadisticas" variants={elemento}>
        {verReportes && (
          <>
            <TarjetaEstadistica
              titulo="Ventas de hoy"
              valor={indicadores ? formatearCOP(indicadores.ventasHoy) : '—'}
              icono={Banknote}
              variacion={indicadores?.variacionHoy}
              detalle={indicadores ? `${indicadores.cantidadHoy} venta(s) · vs. ayer` : undefined}
              cargando={cargando}
            />
            <TarjetaEstadistica
              titulo="Últimos 7 días"
              valor={indicadores ? formatearCOP(indicadores.ventasSiete) : '—'}
              icono={TrendingUp}
              variacion={indicadores?.variacionSiete}
              detalle={indicadores ? `${indicadores.cantidadSiete} venta(s) · vs. 7 días previos` : undefined}
              cargando={cargando}
            />
            <TarjetaEstadistica
              titulo="Últimos 30 días"
              valor={indicadores ? formatearCOP(indicadores.ventasTreinta) : '—'}
              icono={Receipt}
              detalle={indicadores ? `${indicadores.cantidadTreinta} venta(s)` : undefined}
              cargando={cargando}
            />
            <TarjetaEstadistica
              titulo="Ganancia estimada (30 días)"
              valor={indicadores ? formatearCOP(indicadores.gananciaTreinta) : '—'}
              icono={Banknote}
              tono="verde"
              detalle={indicadores ? `7 días: ${formatearCOP(indicadores.gananciaSiete)}` : undefined}
              cargando={cargando}
            />
          </>
        )}
        <TarjetaEstadistica
          titulo="Mesas ocupadas"
          valor={`${formatearNumero(mesasOcupadas)} de ${formatearNumero(mesas.length)}`}
          icono={Armchair}
          detalle={`Pendientes de pago: ${mesasPendientes}`}
          cargando={cargando}
        />
        <TarjetaEstadistica
          titulo="Cuentas abiertas"
          valor={formatearNumero(cuentasAbiertas)}
          icono={ShoppingCart}
          detalle="Ventas sin cobrar"
          cargando={cargando}
        />
        <TarjetaEstadistica
          titulo="Inventario bajo"
          valor={formatearNumero(inventarioBajo.length)}
          icono={PackageX}
          tono={inventarioBajo.length > 0 ? 'rojo' : 'verde'}
          detalle={inventarioBajo.length > 0 ? 'Productos por reponer' : 'Todo en orden'}
          cargando={cargando}
        />
      </motion.div>

      {!verReportes && (
        <motion.p className="texto-suave" variants={elemento}>
          Tu usuario no tiene permiso para ver reportes de ventas. Si lo necesitas, pídeselo al administrador.
        </motion.p>
      )}

      {/* Gráfica y más vendidos (solo con permiso de reportes) */}
      {verReportes && (
        <motion.div className="dash-dos-columnas" variants={elemento}>
          <section className="tarjeta tarjeta-compacta" aria-labelledby="titulo-grafica">
            <div className="dash-seccion-cabecera">
              <h3 id="titulo-grafica">Ventas por día</h3>
              <div className="selector-periodo" role="group" aria-label="Periodo de la gráfica">
                {[7, 14, 30].map((dias) => (
                  <button
                    key={dias}
                    type="button"
                    className={diasGrafica === dias ? 'activo' : ''}
                    onClick={() => setDiasGrafica(dias)}
                  >
                    {dias} d
                  </button>
                ))}
              </div>
            </div>
            {errores.ganancias ? (
              <p className="mensaje-error" role="alert">{errores.ganancias}</p>
            ) : cargando ? (
              <div className="esqueleto" style={{ height: 200 }} />
            ) : serieConVentas ? (
              <GraficaBarras
                datos={serie}
                formatoValor={formatearCOP}
                descripcion={`Ventas diarias de los últimos ${diasGrafica} días`}
              />
            ) : (
              <p className="texto-suave estado-vacio-simple">Aún no hay ventas en este periodo.</p>
            )}
          </section>

          <section className="tarjeta tarjeta-compacta" aria-labelledby="titulo-vendidos">
            <h3 id="titulo-vendidos">Más vendidos (30 días)</h3>
            {errores.masVendidos ? (
              <p className="mensaje-error" role="alert">{errores.masVendidos}</p>
            ) : cargando ? (
              <div className="esqueleto" style={{ height: 160 }} />
            ) : masVendidos.length === 0 ? (
              <p className="texto-suave estado-vacio-simple">Todavía no hay productos vendidos.</p>
            ) : (
              <ol className="lista-ranking">
                {masVendidos.map((producto) => (
                  <li key={producto.Producto}>
                    <div className="ranking-linea">
                      <span>{producto.Producto}</span>
                      <strong>{formatearNumero(producto['Cantidad vendida'])} u.</strong>
                    </div>
                    <div className="ranking-barra">
                      <span style={{ width: `${(producto['Cantidad vendida'] / maximoVendido) * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </motion.div>
      )}

      {/* Inventario bajo y actividad reciente */}
      <motion.div className="dash-dos-columnas" variants={elemento}>
        <section className="tarjeta tarjeta-compacta" aria-labelledby="titulo-stock">
          <h3 id="titulo-stock">Productos por reponer</h3>
          {errores.inventarioBajo ? (
            <p className="mensaje-error" role="alert">{errores.inventarioBajo}</p>
          ) : cargando ? (
            <div className="esqueleto" style={{ height: 120 }} />
          ) : inventarioBajo.length === 0 ? (
            <p className="texto-suave estado-vacio-simple">No hay productos con inventario bajo.</p>
          ) : (
            <ul className="lista-simple">
              {inventarioBajo.slice(0, 6).map((producto) => (
                <li key={producto.id}>
                  <span>{producto.nombre}</span>
                  <span className={producto.stock_actual === 0 ? 'etiqueta rojo' : 'etiqueta ambar'}>
                    {producto.stock_actual} / mín. {producto.stock_minimo}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {verReportes && (
          <section className="tarjeta tarjeta-compacta" aria-labelledby="titulo-actividad">
            <h3 id="titulo-actividad">Actividad reciente</h3>
            {errores.ventas ? (
              <p className="mensaje-error" role="alert">{errores.ventas}</p>
            ) : cargando ? (
              <div className="esqueleto" style={{ height: 120 }} />
            ) : actividad.length === 0 ? (
              <p className="texto-suave estado-vacio-simple">Aún no hay ventas registradas.</p>
            ) : (
              <ul className="lista-simple">
                {actividad.map((venta, indice) => (
                  <li key={`${venta.Fecha}-${indice}`}>
                    <span>
                      {venta.Mesa} · <span className="texto-suave">{formatearFecha(venta.Fecha)}</span>
                    </span>
                    <strong>{formatearCOP(venta.Total)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </motion.div>

      {/* Accesos rápidos */}
      <motion.section variants={elemento} aria-labelledby="titulo-accesos">
        <h3 id="titulo-accesos">Accesos rápidos</h3>
        <div className="dash-accesos">
          {accesos.map((modulo) => {
            const Icono = modulo.icono;
            return (
              <Link key={modulo.ruta} to={modulo.ruta} className="acceso-rapido">
                <Icono size={22} aria-hidden="true" />
                <span>{modulo.etiqueta}</span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            );
          })}
        </div>
      </motion.section>
    </motion.div>
  );
}