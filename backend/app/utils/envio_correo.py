# Ruta: backend/app/utils/envio_correo.py
# Envía la factura de una venta por correo electrónico, con el PDF adjunto,
# usando el servidor SMTP configurado en el archivo .env. No depende de
# ningún proveedor de correo específico: funciona con cualquier servidor
# SMTP estándar (Gmail, Outlook, o un correo corporativo propio).

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import configuracion


class ErrorEnvioCorreo(Exception):
    """
    Se lanza cuando la factura no pudo enviarse por correo (configuración
    incompleta o falla de conexión con el servidor SMTP), para que el router
    la traduzca a una respuesta HTTP clara en vez de un error 500 genérico.
    """


def enviar_factura_por_correo(
    destinatario: str,
    pdf_bytes: bytes,
    nombre_archivo: str,
    numero_venta: int,
) -> None:
    """
    Envía un correo con la factura en PDF adjunta al destinatario indicado.
    Lanza ErrorEnvioCorreo si el módulo no está configurado (SMTP_HOST
    vacío) o si el envío falla por cualquier motivo.
    """
    # Bloque: valida que el envío de correos esté realmente configurado
    # antes de intentar conectarse, para dar un mensaje de error claro.
    if not configuracion.SMTP_HOST or not configuracion.SMTP_REMITENTE:
        raise ErrorEnvioCorreo(
            "El envío de facturas por correo no está configurado. "
            "Define SMTP_HOST, SMTP_USUARIO, SMTP_CONTRASENA y SMTP_REMITENTE en el archivo .env."
        )

    # Bloque: arma el mensaje de correo con el PDF adjunto
    mensaje = MIMEMultipart()
    mensaje["From"] = configuracion.SMTP_REMITENTE
    mensaje["To"] = destinatario
    mensaje["Subject"] = f"Factura de tu compra #{numero_venta} - {configuracion.NOMBRE_NEGOCIO}"

    cuerpo = (
        f"Hola,\n\n"
        f"Gracias por tu compra en {configuracion.NOMBRE_NEGOCIO}. "
        f"Adjunto encontrarás la factura de tu compra #{numero_venta}.\n\n"
        f"Este correo fue generado automáticamente, por favor no respondas a este mensaje.\n\n"
        f"Sistema desarrollado por SoftLegacy - https://softlegacy.vercel.app"
    )
    mensaje.attach(MIMEText(cuerpo, "plain", "utf-8"))

    adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
    adjunto.add_header("Content-Disposition", "attachment", filename=nombre_archivo)
    mensaje.attach(adjunto)

    # Bloque: conecta al servidor SMTP y envía el correo. El "with" garantiza
    # que la conexión se cierre siempre, incluso si el envío falla a mitad de camino.
    try:
        with smtplib.SMTP(configuracion.SMTP_HOST, configuracion.SMTP_PUERTO, timeout=15) as servidor:
            if configuracion.SMTP_USA_TLS:
                servidor.starttls()
            if configuracion.SMTP_USUARIO and configuracion.SMTP_CONTRASENA:
                servidor.login(configuracion.SMTP_USUARIO, configuracion.SMTP_CONTRASENA)
            servidor.sendmail(configuracion.SMTP_REMITENTE, [destinatario], mensaje.as_string())
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorEnvioCorreo(
            "No se pudo enviar el correo. Verifica la configuración SMTP o intenta más tarde."
        ) from error