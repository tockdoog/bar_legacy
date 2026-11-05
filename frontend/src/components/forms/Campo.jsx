// frontend/src/components/forms/Campo.jsx
// Campo de formulario reutilizable: etiqueta, contenedor con foco dorado,
// texto de ayuda y mensaje de error accesible (role="alert").

export default function Campo({ etiqueta, error, ayuda, caja = true, className = '', children }) {
  return (
    <label className={`campo ${className}`}>
      <span>{etiqueta}</span>
      {caja ? <div className={`campo-caja ${error ? 'con-error' : ''}`}>{children}</div> : children}
      {ayuda && !error && <small className="campo-ayuda">{ayuda}</small>}
      {error && <small className="campo-error" role="alert">{error}</small>}
    </label>
  );
}