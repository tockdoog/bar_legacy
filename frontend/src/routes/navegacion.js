// frontend/src/routes/navegacion.js
// Catálogo único de los módulos del sistema: ruta, nombre, icono y el rol o
// permiso necesario para verlos. Lo usan la barra lateral, el encabezado y el
// enrutador, para no repetir esta información en varios archivos.
// Ocultar un módulo es solo comodidad visual: el backend valida cada petición.

import {
  Armchair,
  BarChart3,
  Boxes,
  LayoutDashboard,
  Package,
  Percent,
  Settings,
  ShoppingCart,
  Tags,
  Truck,
  Users,
} from 'lucide-react';

// Bloque: lista de módulos en el orden en que aparecen en el menú
export const MODULOS = [
  { ruta: '/', etiqueta: 'Dashboard', icono: LayoutDashboard },
  { ruta: '/pos', etiqueta: 'Punto de venta', icono: ShoppingCart },
  { ruta: '/mesas', etiqueta: 'Mesas', icono: Armchair },
  { ruta: '/inventario', etiqueta: 'Inventario', icono: Boxes },
  { ruta: '/productos', etiqueta: 'Productos', icono: Package },
  { ruta: '/categorias', etiqueta: 'Categorías', icono: Tags },
  { ruta: '/compras', etiqueta: 'Compras y proveedores', icono: Truck, permiso: 'compras_gestionar' },
  { ruta: '/promociones', etiqueta: 'Promociones', icono: Percent },
  { ruta: '/reportes', etiqueta: 'Reportes', icono: BarChart3, permiso: 'reportes_ver' },
  { ruta: '/usuarios', etiqueta: 'Usuarios', icono: Users, roles: ['administrador'] },
  { ruta: '/configuracion', etiqueta: 'Configuración', icono: Settings, permiso: 'finanzas_gestionar' },
];

// Bloque: indica si el usuario actual puede ver un módulo según su rol y permisos
export function puedeVerModulo(modulo, { esAdmin, tienePermiso }) {
  if (modulo.roles && !modulo.roles.includes(esAdmin ? 'administrador' : 'empleado')) return false;
  if (modulo.permiso && !tienePermiso(modulo.permiso)) return false;
  return true;
}

// Bloque: encuentra el módulo que corresponde a la ruta actual
export function moduloDeRuta(ruta) {
  if (ruta === '/') return MODULOS[0];
  return MODULOS.find((modulo) => modulo.ruta !== '/' && ruta.startsWith(modulo.ruta)) || null;
}