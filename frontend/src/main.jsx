// frontend/src/main.jsx
// Punto de entrada: monta React, la red de seguridad de errores, el enrutador, el
// proveedor de sesión y la configuración global de animaciones (respeta
// "reducir movimiento" del sistema).

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';

import App from './App.jsx';
import ErrorBoundary from './components/common/ErrorBoundary.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('raiz')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </MotionConfig>
    </ErrorBoundary>
  </React.StrictMode>
);