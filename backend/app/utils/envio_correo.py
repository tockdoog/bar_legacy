# Ruta: backend/app/utils/envio_correo.py
# Envía la factura de una venta por correo electrónico, con el PDF adjunto, usando el
# servidor SMTP configurado en las variables de entorno. Funciona con cualquier servidor
# SMTP estándar (Gmail, Outlook o un correo corporativo).
#
# CAMBIOS:
# - El asunto se codifica en UTF-8 (tildes y "ñ") y se eliminan saltos de línea de los
#   datos que entran a las cabeceras (evita la inyección de cabeceras de correo).
# - El puerto 465 usa conexión SSL directa; los demás usan STARTTLS si SMTP_USA_TLS es true.

import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import configuracion

PUERTO_SSL_DIRECTO = 465
SEGUNDOS_LIMITE_SMTP = 15


class ErrorEnvioCorreo(Exception):
    """
    Se lanza cuando la factura no pudo enviarse (configuración incompleta o falla del
    servidor SMTP), para que el router la traduzca a una respuesta HTTP clara.
    """


def _limpiar_cabecera(texto: str) -> str:
    """Quita saltos de línea de un texto que irá en una cabecera del correo."""
    return texto.replace("\r", " ").replace("\n", " ").strip()


def enviar_factura_por_correo(
    destinatario: str,
    pdf_bytes: bytes,
    nombre_archivo: str,
    numero_venta: int,
) -> None:
    """
    Envía un correo con la factura en PDF adjunta. Lanza ErrorEnvioCorreo si el módulo
    no está configurado (SMTP_HOST o SMTP_REMITENTE vacíos) o si el envío falla.
    """
    # Bloque: valida que el envío esté configurado antes de intentar conectarse
    if not configuracion.SMTP_HOST or not configuracion.SMTP_REMITENTE:
        raise ErrorEnvioCorreo(
            "El envío de facturas por correo no está configurado. "
            "Define SMTP_HOST, SMTP_USUARIO, SMTP_CONTRASENA y SMTP_REMITENTE en las variables de entorno."
        )

    destinatario_limpio = _limpiar_cabecera(destinatario)
    if not destinatario_limpio or "," in destinatario_limpio or ";" in destinatario_limpio:
        raise ErrorEnvioCorreo("El correo del destinatario no es válido.")

    nombre_negocio = _limpiar_cabecera(configuracion.NOMBRE_NEGOCIO)

    # Bloque: arma el mensaje con el PDF adjunto
    mensaje = MIMEMultipart()
    mensaje["From"] = _limpiar_cabecera(configuracion.SMTP_REMITENTE)
    mensaje["To"] = destinatario_limpio
    mensaje["Subject"] = Header(f"Factura de tu compra #{numero_venta} - {nombre_negocio}", "utf-8")

    cuerpo = (
        f"Hola,\n\n"
        f"Gracias por tu compra en {nombre_negocio}. "
        f"Adjunto encontrarás la factura de tu compra #{numero_venta}.\n\n"
        f"Este correo fue generado automáticamente, por favor no respondas a este mensaje.\n\n"
        f"Sistema desarrollado por SoftLegacy - https://softlegacy.vercel.app"
    )
    mensaje.attach(MIMEText(cuerpo, "plain", "utf-8"))

    adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
    adjunto.add_header("Content-Disposition", "attachment", filename=nombre_archivo)
    mensaje.attach(adjunto)

    # Bloque: conecta y envía. El "with" cierra la conexión siempre, aunque falle a mitad de camino.
    try:
        if configuracion.SMTP_PUERTO == PUERTO_SSL_DIRECTO:
            servidor_smtp = smtplib.SMTP_SSL(
                configuracion.SMTP_HOST, configuracion.SMTP_PUERTO, timeout=SEGUNDOS_LIMITE_SMTP
            )
        else:
            servidor_smtp = smtplib.SMTP(
                configuracion.SMTP_HOST, configuracion.SMTP_PUERTO, timeout=SEGUNDOS_LIMITE_SMTP
            )

        with servidor_smtp as servidor:
            if configuracion.SMTP_PUERTO != PUERTO_SSL_DIRECTO and configuracion.SMTP_USA_TLS:
                servidor.starttls()
            if configuracion.SMTP_USUARIO and configuracion.SMTP_CONTRASENA:
                servidor.login(configuracion.SMTP_USUARIO, configuracion.SMTP_CONTRASENA)
            servidor.sendmail(configuracion.SMTP_REMITENTE, [destinatario_limpio], mensaje.as_string())
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorEnvioCorreo(
            "No se pudo enviar el correo. Verifica la configuración SMTP o intenta más tarde."
        ) from error