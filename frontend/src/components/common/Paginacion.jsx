// frontend/src/components/common/Paginacion.jsx
// Controles de paginación: rango mostrado, página actual y botones anterior/siguiente.

import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function Paginacion({ pagina, totalPaginas, total, tamano, onCambiar }) {
  if (total === 0) return null;
  const desde = (pagina - 1) * tamano + 1;
  const hasta = Math.min(pagina * tamano, total);

  return (
    <nav className="paginacion" aria-label="Paginación">
      <span className="texto-suave">Mostrando {desde}–{hasta} de {total}</span>
      {totalPaginas > 1 && (
        <div className="paginacion-controles">
          <button type="button" className="boton boton-secundario boton-compacto" onClick={() => onCambiar(pagina - 1)} disabled={pagina <= 1} aria-label="Página anterior">
            <ChevronLeft size={18} />
          </button>
          <span>Página {pagina} de {totalPaginas}</span>
          <button type="button" className="boton boton-secundario boton-compacto" onClick={() => onCambiar(pagina + 1)} disabled={pagina >= totalPaginas} aria-label="Página siguiente">
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </nav>
  );
}