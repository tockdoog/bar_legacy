// frontend/src/pages/auth/Login.jsx
// Pantalla de inicio de sesión de Bar Legacy: validación básica, mostrar u
// ocultar contraseña, mensajes de error claros (credenciales, cuenta bloqueada,
// límite de intentos, conexión) y animación sutil de entrada.

import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Loader2, LogIn, Lock, User } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext.jsx';
import { mensajeDeError, urlApi } from '../../services/api.js';

export default function Login() {
  const { iniciarSesion } = useAuth();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const destino = ubicacion.state?.desde?.pathname || '/';

  const [usuario, setUsuario] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [verContrasena, setVerContrasena] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [logoDisponible, setLogoDisponible] = useState(true);

  // Bloque: valida los campos, inicia sesión y redirige al destino original
  async function manejarEnvio(evento) {
    evento.preventDefault();
    setError('');

    if (usuario.trim().length < 3) {
      setError('Ingresa tu nombre de usuario (mínimo 3 caracteres).');
      return;
    }
    if (!contrasena) {
      setError('Ingresa tu contraseña.');
      return;
    }

    setEnviando(true);
    try {
      await iniciarSesion(usuario.trim(), contrasena);
      toast.success('Bienvenido a Bar Legacy');
      navegar(destino, { replace: true });
    } catch (fallo) {
      setError(mensajeDeError(fallo));
      setContrasena('');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login-fondo">
      <motion.section
        className="tarjeta login-tarjeta"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        aria-labelledby="titulo-login"
      >
        {/* Logo servido por el backend; si no existe, se muestra solo el texto de marca */}
        {logoDisponible && (
          <img
            className="login-logo"
            src={`${urlApi}/imagenes/logo.png`}
            alt="Logotipo de Bar Legacy"
            onError={() => setLogoDisponible(false)}
          />
        )}
        <h1 id="titulo-login" className="titulo-marca">
          Bar <span>Legacy</span>
        </h1>
        <hr className="divisor-dorado" />
        <p className="texto-suave">Ingresa con tu cuenta para abrir el punto de venta.</p>

        <form onSubmit={manejarEnvio} noValidate>
          <label className="campo">
            <span>Usuario</span>
            <div className="campo-caja">
              <User size={18} aria-hidden="true" />
              <input
                type="text"
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                maxLength={50}
                disabled={enviando}
                required
              />
            </div>
          </label>

          <label className="campo">
            <span>Contraseña</span>
            <div className="campo-caja">
              <Lock size={18} aria-hidden="true" />
              <input
                type={verContrasena ? 'text' : 'password'}
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                autoComplete="current-password"
                maxLength={72}
                disabled={enviando}
                required
              />
              <button
                type="button"
                className="boton-icono"
                onClick={() => setVerContrasena((v) => !v)}
                aria-label={verContrasena ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                {verContrasena ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>

          {error && (
            <p className="mensaje-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="boton boton-primario boton-completo" disabled={enviando}>
            {enviando ? <Loader2 className="girar" size={18} /> : <LogIn size={18} />}
            {enviando ? 'Verificando…' : 'Iniciar sesión'}
          </button>
        </form>
      </motion.section>
    </main>
  );
}