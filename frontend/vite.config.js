// frontend/vite.config.js
// Configuración de Vite: plugin de React, puerto de desarrollo y separación
// de dependencias pesadas en bloques aparte para acelerar la carga en Vercel.

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    // No se publican mapas de código fuente en producción (menos exposición)
    sourcemap: false,
    rollupOptions: {
      output: {
        // Separa librerías grandes para que el navegador las cachee por separado
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          animacion: ['framer-motion'],
        },
      },
    },
  },
});