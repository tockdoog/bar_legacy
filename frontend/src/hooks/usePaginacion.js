// frontend/src/hooks/usePaginacion.js
// Paginación del lado del cliente (el backend no pagina). Ajusta la página
// actual si la lista se acorta; "reiniciar" vuelve a la primera (al filtrar).

import { useMemo, useState } from 'react';

export default function usePaginacion(lista, tamano = 10) {
  const [pagina, setPagina] = useState(1);
  const totalPaginas = Math.max(Math.ceil(lista.length / tamano), 1);
  const actual = Math.min(pagina, totalPaginas);

  const items = useMemo(
    () => lista.slice((actual - 1) * tamano, actual * tamano),
    [lista, actual, tamano]
  );

  return {
    pagina: actual,
    totalPaginas,
    total: lista.length,
    tamano,
    items,
    irAPagina: setPagina,
    reiniciar: () => setPagina(1),
  };
}