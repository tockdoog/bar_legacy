// frontend/src/utils/imagen.js
// Reduce una foto en el navegador antes de subirla: máximo 1000 px de lado y
// JPEG de calidad 0,85. Una foto de celular de 8 MB queda en unos 200 KB. Es
// necesario en Vercel, que rechaza peticiones de más de 4,5 MB; además ahorra
// datos móviles y espacio en la base de datos.

// Bloque: devuelve un File JPEG optimizado a partir de la imagen elegida
export async function comprimirImagen(archivo, ladoMaximo = 1000, calidad = 0.85) {
  const bitmap = await createImageBitmap(archivo);
  const escala = Math.min(1, ladoMaximo / Math.max(bitmap.width, bitmap.height));
  const lienzo = document.createElement('canvas');
  lienzo.width = Math.max(Math.round(bitmap.width * escala), 1);
  lienzo.height = Math.max(Math.round(bitmap.height * escala), 1);

  // Fondo blanco: JPEG no admite transparencia (los PNG transparentes quedarían negros)
  const contexto = lienzo.getContext('2d');
  contexto.fillStyle = '#ffffff';
  contexto.fillRect(0, 0, lienzo.width, lienzo.height);
  contexto.drawImage(bitmap, 0, 0, lienzo.width, lienzo.height);
  bitmap.close?.();

  const blob = await new Promise((resolver) => lienzo.toBlob(resolver, 'image/jpeg', calidad));
  if (!blob) throw new Error('No se pudo procesar la imagen.');
  return new File([blob], 'producto.jpg', { type: 'image/jpeg' });
}