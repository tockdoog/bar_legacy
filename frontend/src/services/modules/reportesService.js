// frontend/src/services/modules/reportesService.js
// Servicios de reportes (app/routers/reportes.py): consulta en pantalla (JSON) y
// exportación a PDF o Excel. Todo exige el permiso "reportes_ver". Las fechas
// van como AAAA-MM-DD (día de Colombia).

import api from '../api.js';

// Bloque: reporte en JSON { titulo, columnas, columnas_moneda, filas, resumen }
export async function obtenerReporte(tipo, desde, hasta) {
  const { data } = await api.get(`/api/reportes/${tipo}`, {
    params: { fecha_inicio: desde, fecha_fin: hasta },
  });
  return data;
}

// Bloque: descarga el reporte como archivo. "formato" es "pdf" o "excel".
export async function descargarReporte(tipo, formato, desde, hasta) {
  let respuesta;
  try {
    respuesta = await api.get(`/api/reportes/${tipo}/${formato}`, {
      params: { fecha_inicio: desde, fecha_fin: hasta },
      responseType: 'blob',
      timeout: 60000,
    });
  } catch (error) {
    // Con responseType blob el error también llega como Blob: se lee para mostrar el mensaje real
    if (error.response?.data instanceof Blob) {
      try {
        error.response.data = JSON.parse(await error.response.data.text());
      } catch {
        // Si no es JSON, se conserva el error original
      }
    }
    throw error;
  }

  const extension = formato === 'excel' ? 'xlsx' : 'pdf';
  const url = URL.createObjectURL(respuesta.data);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = `reporte_${tipo}.${extension}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}