// frontend/src/hooks/usePedido.js
// Manejo del carrito del POS en sus dos modos:
// - Cuenta de mesa (ventaId): el carrito vive en el backend y cada cambio se
//   guarda al instante. Las operaciones se hacen en cola para que un escaneo
//   rápido no mezcle respuestas.
// - Venta rápida (sin ventaId): el carrito vive en el navegador y solo se
//   envía al backend al cobrar.
// Valida el stock antes de agregar (el backend solo lo valida al cobrar).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { mensajeDeError } from '../services/api.js';
import * as ventas from '../services/modules/ventasService.js';

export default function usePedido(ventaId, productos) {
  const [venta, setVenta] = useState(null);
  const [itemsLocales, setItemsLocales] = useState([]);
  const [cargando, setCargando] = useState(Boolean(ventaId));
  const [ocupado, setOcupado] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const cola = useRef(Promise.resolve());

  // Bloque: carga la cuenta de la mesa desde el backend
  const recargar = useCallback(async () => {
    if (!ventaId) {
      setVenta(null);
      setCargando(false);
      return;
    }
    setCargando(true);
    setErrorCarga('');
    try {
      const datos = await ventas.obtenerVenta(ventaId);
      if (datos.estado !== 'abierta') setErrorCarga('Esta cuenta ya fue cerrada.');
      else setVenta(datos);
    } catch (error) {
      setErrorCarga(mensajeDeError(error));
    } finally {
      setCargando(false);
    }
  }, [ventaId]);

  useEffect(() => {
    recargar();
  }, [recargar]);

  // Bloque: líneas normalizadas del carrito, sin importar el modo
  const lineas = useMemo(() => {
    if (ventaId) {
      return (venta?.detalles || []).map((d) => ({
        clave: `d${d.id}`,
        detalleId: d.id,
        productoId: d.producto_id,
        nombre: d.nombre_producto,
        promocion: d.nombre_promocion,
        precio: d.precio_venta_unitario,
        cantidad: d.cantidad,
        subtotal: d.subtotal,
      }));
    }
    return itemsLocales.map((item) => ({
      clave: `${item.tipo}${item.id}`,
      productoId: item.tipo === 'producto' ? item.id : null,
      nombre: item.nombre,
      promocion: item.tipo === 'promocion' ? 'Promoción' : null,
      precio: item.precio,
      cantidad: item.cantidad,
      subtotal: Math.round(item.precio * item.cantidad * 100) / 100,
    }));
  }, [ventaId, venta, itemsLocales]);

  const total = ventaId
    ? venta?.total ?? 0
    : lineas.reduce((suma, linea) => suma + linea.subtotal, 0);
  const cantidadTotal = lineas.reduce((suma, linea) => suma + linea.cantidad, 0);

  // Bloque: unidades de un producto que ya están en el carrito
  const unidadesEnCarrito = (productoId) =>
    lineas.filter((l) => l.productoId === productoId).reduce((suma, l) => suma + l.cantidad, 0);

  // Bloque: ejecuta una operación del backend en cola y actualiza la venta con su respuesta
  const ejecutar = (accion) => {
    cola.current = cola.current.then(async () => {
      setOcupado(true);
      try {
        const respuesta = await accion();
        if (respuesta) setVenta(respuesta);
      } catch (error) {
        toast.error(mensajeDeError(error));
      } finally {
        setOcupado(false);
      }
    });
    return cola.current;
  };

  // Bloque: agrega una unidad de un producto validando existencias
  const agregarProducto = (producto) => {
    if (producto.stock_actual <= 0) {
      toast.error(`"${producto.nombre}" está agotado.`);
      return;
    }
    if (unidadesEnCarrito(producto.id) + 1 > producto.stock_actual) {
      toast.warning(`Solo hay ${producto.stock_actual} unidad(es) de "${producto.nombre}".`);
      return;
    }
    if (ventaId) {
      ejecutar(() => ventas.agregarProducto(ventaId, producto.id, 1));
      return;
    }
    setItemsLocales((previo) => {
      const existe = previo.some((i) => i.tipo === 'producto' && i.id === producto.id);
      if (existe) {
        return previo.map((i) =>
          i.tipo === 'producto' && i.id === producto.id ? { ...i, cantidad: i.cantidad + 1 } : i
        );
      }
      return [
        ...previo,
        { tipo: 'producto', id: producto.id, nombre: producto.nombre, precio: producto.precio_venta, cantidad: 1 },
      ];
    });
  };

  // Bloque: agrega una promoción (combo). El backend valida el stock al cobrar.
  const agregarPromocion = (promocion) => {
    if (ventaId) {
      ejecutar(() => ventas.agregarPromocion(ventaId, promocion.id, 1));
      return;
    }
    setItemsLocales((previo) => {
      const existe = previo.some((i) => i.tipo === 'promocion' && i.id === promocion.id);
      if (existe) {
        return previo.map((i) =>
          i.tipo === 'promocion' && i.id === promocion.id ? { ...i, cantidad: i.cantidad + 1 } : i
        );
      }
      return [
        ...previo,
        { tipo: 'promocion', id: promocion.id, nombre: promocion.nombre, precio: promocion.precio_promocional, cantidad: 1 },
      ];
    });
  };

  // Bloque: quita una línea del carrito
  const quitar = (linea) => {
    if (ventaId) {
      ejecutar(() => ventas.eliminarItem(ventaId, linea.detalleId));
      return;
    }
    setItemsLocales((previo) => previo.filter((i) => `${i.tipo}${i.id}` !== linea.clave));
  };

  // Bloque: cambia la cantidad de una línea (menos de 1 la elimina)
  const cambiarCantidad = (linea, cantidad) => {
    if (cantidad < 1) {
      quitar(linea);
      return;
    }
    if (linea.productoId) {
      const producto = productos.find((p) => p.id === linea.productoId);
      const otras = unidadesEnCarrito(linea.productoId) - linea.cantidad;
      if (producto && otras + cantidad > producto.stock_actual) {
        toast.warning(`Solo hay ${producto.stock_actual} unidad(es) de "${producto.nombre}".`);
        return;
      }
    }
    if (ventaId) {
      ejecutar(() => ventas.actualizarCantidad(ventaId, linea.detalleId, cantidad));
      return;
    }
    setItemsLocales((previo) =>
      previo.map((i) => (`${i.tipo}${i.id}` === linea.clave ? { ...i, cantidad } : i))
    );
  };

  // Bloque: vacía el carrito completo
  const vaciar = () => {
    if (!ventaId) {
      setItemsLocales([]);
      return;
    }
    ejecutar(async () => {
      let ultima = venta;
      for (const linea of lineas) {
        ultima = await ventas.eliminarItem(ventaId, linea.detalleId);
      }
      return ultima;
    });
  };

  return {
    venta,
    lineas,
    total,
    cantidadTotal,
    cargando,
    ocupado,
    errorCarga,
    itemsLocales,
    limpiarLocal: () => setItemsLocales([]),
    recargar,
    agregarProducto,
    agregarPromocion,
    cambiarCantidad,
    quitar,
    vaciar,
  };
}