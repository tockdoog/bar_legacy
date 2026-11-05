# Ruta: backend/app/permisos.py
# Catálogo único de permisos granulares que el administrador puede asignar a
# un usuario con rol de empleado. Es la única fuente de verdad: tanto el
# backend (dependencies.py, routers) como el frontend (a través del endpoint
# GET /api/usuarios/permisos-disponibles) leen de aquí, para no mantener la
# misma lista duplicada en varios lugares. Un administrador NUNCA necesita
# estos permisos: su rol ya le da acceso completo al sistema.
#
# Para habilitar un permiso nuevo en otro módulo (promociones, etc.):
#   1. Agrega la clave y su descripción en CATALOGO_PERMISOS.
#   2. En el router de ese módulo, cambia el Depends(requerir_rol(...)) del
#      endpoint por Depends(requerir_permiso("clave_del_permiso")).

CATALOGO_PERMISOS: dict[str, str] = {
    "inventario_gestionar": "Crear, editar y eliminar productos del inventario",
    "compras_gestionar": "Registrar compras a proveedores y gestionar el catálogo de proveedores",
    "ventas_anular": "Anular ventas que ya fueron cobradas",
    "reportes_ver": "Consultar y descargar los reportes de ventas, compras y ganancias del negocio",
    "finanzas_gestionar": "Configurar impuestos y margen, y consultar el análisis financiero del negocio",
}


def es_permiso_valido(clave: str) -> bool:
    """Indica si una clave de permiso existe en el catálogo del sistema."""
    return clave in CATALOGO_PERMISOS