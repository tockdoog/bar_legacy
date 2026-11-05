// frontend/src/components/forms/BuscadorProducto.jsx
// Buscador de productos con lista de resultados, reutilizado en Compras y
// Promociones. Busca por nombre o código de barras (sin importar tildes ni
// mayúsculas). Enter elige el primer resultado, y un código exacto va primero,
// así que sirve también para pegar o escribir un código.

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';

import { normalizar } from '../../utils/texto.js';

export default function BuscadorProducto({ productos, onElegir, placeholder = 'Buscar producto por nombre o código…', deshabilitado = false }) {
  const [texto, setTexto] = useState('');

  // Bloque: hasta 8 coincidencias; si el texto es un código exacto, ese producto va primero
  const resultados = useMemo(() => {
    const buscado = normalizar(texto.trim());
    if (!buscado) return [];
    return productos
      .filter((p) => normalizar(p.nombre).includes(buscado) || normalizar(p.codigo_barras).includes(buscado))
      .sort((a, b) => Number(normalizar(b.codigo_barras) === buscado) - Number(normalizar(a.codigo_barras) === buscado))
      .slice(0, 8);
  }, [productos, texto]);

  const elegir = (producto) => {
    onElegir(producto);
    setTexto('');
  };

  const alTeclear = (evento) => {
    if (evento.key !== 'Enter') return;
    evento.preventDefault(); // Evita enviar el formulario al presionar Enter
    if (resultados.length > 0) elegir(resultados[0]);
  };

  return (
    <div className="buscador-producto">
      <div className="campo-caja">
        <Search size={18} aria-hidden="true" />
        <input
          type="search"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={alTeclear}
          placeholder={placeholder}
          aria-label="Buscar producto para agregar"
          maxLength={64}
          autoComplete="off"
          disabled={deshabilitado}
        />
      </div>
      {texto.trim() && (
        <ul className="buscador-resultados">
          {resultados.length === 0 ? (
            <li className="texto-suave sin-resultados">No hay productos con ese criterio.</li>
          ) : (
            resultados.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => elegir(p)}>
                  <strong>{p.nombre}</strong>
                  <span className="texto-suave">
                    {[p.codigo_barras, `${p.stock_actual} disp.`].filter(Boolean).join(' · ')}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}