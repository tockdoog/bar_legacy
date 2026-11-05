// frontend/src/hooks/useProveedores.js
// Carga la lista de proveedores y la comparte entre las pestañas de Compras.

import { useCallback, useEffect, useState } from 'react';

import { mensajeDeError } from '../services/api.js';
import { listarProveedores } from '../services/modules/proveedoresService.js';

export default function useProveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  // Bloque: "silencioso" refresca sin mostrar el estado de carga
  const recargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    try {
      setProveedores(await listarProveedores());
      setError('');
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  return { proveedores, cargando, error, recargar };
}