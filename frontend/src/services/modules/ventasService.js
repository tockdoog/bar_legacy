// frontend/src/services/modules/ventasService.js
// Servicios del punto de venta: abrir venta, carrito, cobro, cancelación y
// facturación. Rutas exactas de app/routers/ventas.py.
//
// CORRECCIÓN: al descargar el PDF se pide la respuesta como archivo binario; si el
// servidor responde con un error, el mensaje llegaba como Blob y el usuario veía un
// texto genérico. Ahora se lee el mensaje real del servidor antes de lanzar el error.

import api from '../api.js';

// Bloque: abre una venta (con mesa_id es de mesa; sin él, venta rápida)
export async function abrirVenta(mesaId = null) {
  const { data } = await api.post('/api/ventas/', { mesa_id: mesaId });
  return data;
}

export async function obtenerVenta(ventaId) {
  const { data } = await api.get(`/api/ventas/${ventaId}`);
  return data;
}

export async function listarVentasAbiertas() {
  const { data } = await api.get('/api/ventas/abiertas');
  return data;
}

// Bloque: operaciones sobre el carrito de una venta abierta (todas devuelven la venta actualizada)
export async function agregarProducto(ventaId, productoId, cantidad) {
  const { data } = await api.post(`/api/ventas/${ventaId}/items`, {
    producto_id: productoId,
    cantidad,
  });
  return data;
}

export async function agregarPromocion(ventaId, promocionId, cantidad) {
  const { data } = await api.post(`/api/ventas/${ventaId}/promociones`, {
    promocion_id: promocionId,
    cantidad,
  });
  return data;
}

export async function actualizarCantidad(ventaId, detalleId, cantidad) {
  const { data } = await api.put(`/api/ventas/${ventaId}/items/${detalleId}`, { cantidad });
  return data;
}

export async function eliminarItem(ventaId, detalleId) {
  const { data } = await api.delete(`/api/ventas/${ventaId}/items/${detalleId}`);
  return data;
}

// Bloque: marca la mesa como "pendiente de pago" (el cliente pidió la cuenta)
export async function marcarPendientePago(ventaId) {
  const { data } = await api.post(`/api/ventas/${ventaId}/marcar-pendiente-pago`);
  return data;
}

// Bloque: cobra la venta. "pagos" es [{ metodo_pago, monto }] (uno o varios métodos)
export async function pagarVenta(ventaId, pagos) {
  const { data } = await api.post(`/api/ventas/${ventaId}/pagar`, { pagos });
  return data;
}

// Bloque: cancela una cuenta abierta sin cobrar (libera la mesa; no toca el inventario)
export async function cancelarVenta(ventaId) {
  await api.delete(`/api/ventas/${ventaId}`);
}

// Bloque: venta rápida. Crea la venta, agrega los ítems locales y cobra. Si algo
// falla después de abrirla, la cancela para no dejar cuentas abiertas huérfanas.
export async function registrarVentaRapida(items, pagos) {
  const venta = await abrirVenta(null);
  try {
    for (const item of items) {
      if (item.tipo === 'promocion') await agregarPromocion(venta.id, item.id, item.cantidad);
      else await agregarProducto(venta.id, item.id, item.cantidad);
    }
    return await pagarVenta(venta.id, pagos);
  } catch (error) {
    try {
      await cancelarVenta(venta.id);
    } catch {
      // Si la cancelación también falla, el error original es el que importa
    }
    throw error;
  }
}

// Bloque: datos de la factura para imprimir la tirilla desde el navegador
export async function obtenerDatosFactura(ventaId) {
  const { data } = await api.get(`/api/ventas/${ventaId}/factura`);
  return data;
}

// Bloque: cuando se pide un archivo (blob) y el servidor responde con error, el cuerpo
// del error también llega como Blob. Se convierte a JSON para que mensajeDeError
// (api.js) pueda mostrar el mensaje real en español.
async function leerErrorDeBlob(error) {
  const cuerpo = error?.response?.data;
  if (cuerpo instanceof Blob) {
    try {
      error.response.data = JSON.parse(await cuerpo.text());
    } catch {
      // Si no es JSON, se deja el error tal cual
    }
  }
  return error;
}

// Bloque: descarga la factura en PDF (se pide como archivo binario con el token)
export async function descargarFacturaPdf(ventaId) {
  let datos;
  try {
    const respuesta = await api.get(`/api/ventas/${ventaId}/factura/pdf`, { responseType: 'blob' });
    datos = respuesta.data;
  } catch (error) {
    throw await leerErrorDeBlob(error);
  }

  const url = URL.createObjectURL(datos);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = `factura_${ventaId}.pdf`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// Bloque: envía la factura en PDF al correo del cliente
export async function enviarFacturaCorreo(ventaId, correo) {
  const { data } = await api.post(`/api/ventas/${ventaId}/factura/enviar-correo`, { correo });
  return data;
}