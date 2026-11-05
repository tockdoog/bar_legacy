# Ruta: backend/app/suscripcion/cuentas_proveedor.py
# Catálogo de cuentas/medios de pago del PROVEEDOR del software (tú), NO del
# negocio/cliente que usa el sistema. Esta lista la edita únicamente quien
# desarrolla y comercializa el sistema, para indicarle a sus clientes cómo
# pagar la suscripción mensual. No se gestiona desde ninguna interfaz web ni
# se guarda en base de datos: es configuración estática de código, a
# propósito, para que el administrador del negocio no pueda verla ni
# modificarla desde la aplicación.
#
# Para agregar, editar o quitar una cuenta:
#   1. Si la cuenta tiene código QR, coloca la imagen en:
#        backend/imagenes/cuentas/
#      Ejemplo: backend/imagenes/cuentas/codigo_qr_nequi.png
#   2. Agrega o edita una entrada en la lista CUENTAS_PROVEEDOR de abajo,
#      usando en "archivo_imagen" SOLO EL NOMBRE DEL ARCHIVO (sin carpetas,
#      sin barra inicial), exactamente igual a como lo guardaste en el paso
#      1. NUNCA una ruta completa: el backend arma la ruta final uniendo
#      CARPETA_IMAGENES_CUENTAS_PROVEEDOR (definida en config.py) con este
#      nombre; si aquí se pone una ruta absoluta, Python la interpreta como
#      ruta del sistema operativo completa e ignora la carpeta configurada,
#      por lo que el archivo nunca se encuentra.
#   3. Reinicia el servidor para que el cambio se refleje.
#
#   Correcto:   "archivo_imagen": "codigo_qr_nequi.png"
#   Incorrecto: "archivo_imagen": "/backend/imagenes/cuentas/codigo_qr_nequi.png"

CUENTAS_PROVEEDOR = [
    {
        "nombre": "Nequi",
        "tipo_dato": "Número de celular",
        "valor": "305 285 1155",
        "archivo_imagen": "codigo_qr_nequi.png",
    },
    {
        "nombre": "Bancolombia",
        "tipo_dato": "Cuenta de ahorros",
        "valor": "91286473526",
        "archivo_imagen": "codigo_qr_bancolombia.png",
    },
    {
        "nombre": "Nu",
        "tipo_dato": "Llave",
        "valor": "@JOH140",
        "archivo_imagen": None,
    },
    {
        "nombre": "PayPal",
        "tipo_dato": "Correo electrónico",
        "valor": "tockdoog@gmail.com",
        "archivo_imagen": "codigo_qr_paypal.png",
    },
]