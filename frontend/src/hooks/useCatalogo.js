// frontend/src/hooks/useCatalogo.js
// Carga productos y categorías en paralelo y expone utilidades derivadas
// (nombre de categoría por id y lista de presentaciones usadas). Lo comparten
// las pantallas de Productos, Inventario y Categorías.

import { useCallback, useEffect, useMemo, useState } from 'react';

import { mensajeDeError } from '../services/api.js';
import { listarCategorias, listarProductos } from '../services/modules/catalogoService.js';

export default function useCatalogo() {
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  // Bloque: carga todo; "silencioso" refresca sin mostrar el estado de carga
  const recargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    const [prod, cat] = await Promise.allSettled([listarProductos(), listarCategorias()]);
    if (prod.status === 'fulfilled') {
      setProductos(prod.value);
      setError('');
    } else {
      setError(mensajeDeError(prod.reason));
    }
    if (cat.status === 'fulfilled') setCategorias(cat.value);
    setCargando(false);
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  const nombreCategoria = useMemo(
    () => Object.fromEntries(categorias.map((c) => [c.id, c.nombre])),
    [categorias]
  );

  // Bloque: presentaciones distintas que ya usan los productos (texto libre en el backend)
  const presentaciones = useMemo(() => {
    const conteo = new Map();
    productos.forEach((p) => {
      const nombre = (p.presentacion || '').trim();
      if (nombre) conteo.set(nombre, (conteo.get(nombre) || 0) + 1);
    });
    return [...conteo.entries()]
      .map(([nombre, cantidad]) => ({ nombre, cantidad }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
  }, [productos]);

  return { productos, categorias, nombreCategoria, presentaciones, cargando, error, recargar };
}