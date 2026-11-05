// frontend/src/components/layout/Encabezado.jsx
// Encabezado superior: botón de menú (móvil), título del módulo actual, fecha y
// hora de Bogotá, datos del usuario y botón para cerrar sesión.

import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { LogOut, Menu } from 'lucide-react';

import { useAuth } from '../../context/AuthContext.jsx';
import { moduloDeRuta } from '../../routes/navegacion.js';
import { horaActualBogota } from '../../utils/formato.js';

// Bloque: fecha larga en español en zona horaria de Bogotá (ej. "miércoles, 4 de noviembre")
function fechaLargaBogota() {
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: 'America/Bogota',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date());
}

export default function Encabezado({ onAbrirMenu }) {
  const { usuario, esAdmin, cerrarSesion } = useAuth();
  const ubicacion = useLocation();
  const modulo = moduloDeRuta(ubicacion.pathname);

  // Bloque: reloj que se actualiza cada 30 segundos
  const [reloj, setReloj] = useState({ hora: horaActualBogota(), fecha: fechaLargaBogota() });
  useEffect(() => {
    const temporizador = setInterval(
      () => setReloj({ hora: horaActualBogota(), fecha: fechaLargaBogota() }),
      30000
    );
    return () => clearInterval(temporizador);
  }, []);

  return (
    <header className="encabezado">
      <button type="button" className="boton-icono encabezado-menu" onClick={onAbrirMenu} aria-label="Abrir menú">
        <Menu size={24} />
      </button>

      <div className="encabezado-titulo">
        <h1>{modulo?.etiqueta || 'Bar Legacy'}</h1>
        <p className="texto-suave">{reloj.fecha} · {reloj.hora}</p>
      </div>

      <div className="encabezado-usuario">
        <div className="encabezado-datos">
          <strong>{usuario.nombre_completo}</strong>
          <span className="texto-suave">{esAdmin ? 'Administrador' : 'Empleado'}</span>
        </div>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={cerrarSesion}>
          <LogOut size={18} aria-hidden="true" />
          <span className="solo-escritorio">Salir</span>
        </button>
      </div>
    </header>
  );
}