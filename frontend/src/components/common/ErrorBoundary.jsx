// frontend/src/components/common/ErrorBoundary.jsx
// Red de seguridad de la interfaz: si un componente falla al dibujarse, en vez de
// dejar la pantalla en blanco muestra un mensaje y un botón para recargar. Los
// detalles del error solo se escriben en la consola del navegador.

import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { fallo: false };
  }

  static getDerivedStateFromError() {
    return { fallo: true };
  }

  componentDidCatch(error) {
    console.error('Error de interfaz:', error);
  }

  render() {
    if (!this.state.fallo) return this.props.children;
    return (
      <main className="pantalla-centrada" role="alert">
        <h1 className="titulo-marca">Algo salió <span>mal</span></h1>
        <p className="texto-suave">Ocurrió un error inesperado en la pantalla. Tus datos guardados no se perdieron.</p>
        <button type="button" className="boton boton-primario" onClick={() => window.location.assign('/')}>
          Volver al inicio
        </button>
      </main>
    );
  }
}