"""Email service using SMTP (Google Workspace)."""

from __future__ import annotations

import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from chatbot.core.config import config

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when an email sending operation fails."""


async def _send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP with a 30-second timeout."""
    msg = MIMEMultipart("alternative")
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=config.SMTP_HOST,
        port=config.SMTP_PORT,
        username=config.SMTP_USER,
        password=config.SMTP_PASSWORD,
        start_tls=True,
        timeout=30,
    )


def _build_demo_invitation_html(
    recipient_name: str,
    scheduled_at: datetime,
    duration_minutes: int,
    description: str,
    calendar_link: str,
) -> str:
    formatted_date = scheduled_at.strftime("%A %d de %B de %Y")
    formatted_time = scheduled_at.strftime("%H:%M") + " hs"

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background-color: #f9f9f9; border-radius: 8px; padding: 30px;">
    <h2 style="color: #2c3e50; margin-bottom: 4px;">¡Tu demo de Viventi está confirmada!</h2>
    <hr style="border: none; border-top: 2px solid #e74c3c; margin: 16px 0;">

    <p>Hola {recipient_name},</p>
    <p>Te confirmamos tu sesión de demostración con el equipo de <strong>Viventi</strong>.</p>

    <div style="background: #fff; border-left: 4px solid #e74c3c; padding: 16px; margin: 20px 0; border-radius: 4px;">
      <p style="margin: 4px 0;"><strong>📅 Fecha:</strong> {formatted_date}</p>
      <p style="margin: 4px 0;"><strong>🕐 Hora:</strong> {formatted_time}</p>
      <p style="margin: 4px 0;"><strong>⏱ Duración:</strong> {duration_minutes} minutos</p>
    </div>

    <p>{description}</p>

    <div style="text-align: center; margin: 30px 0;">
      <a href="{calendar_link}"
         style="background-color: #e74c3c; color: white; padding: 12px 28px;
                text-decoration: none; border-radius: 6px; font-weight: bold;
                display: inline-block;">
        Ver evento en Google Calendar
      </a>
    </div>

    <p style="font-size: 13px; color: #777;">
      Si tenés alguna pregunta antes de la demo, podés responder este email o
      contactarnos directamente.
    </p>

    <p>¡Nos vemos pronto!<br>
    <strong>Equipo Viventi</strong></p>
  </div>
</body>
</html>
"""


async def send_demo_invitation(
    to_email: str,
    recipient_name: str,
    scheduled_at: datetime,
    duration_minutes: int,
    description: str,
    calendar_link: str,
) -> None:
    """Send a demo invitation email via SMTP."""
    logger.info("[email_service] Sending demo invitation to %s", to_email)

    formatted_date = scheduled_at.strftime("%d/%m/%Y a las %H:%M")
    subject = f"Tu demo de Viventi — {formatted_date} hs"

    html_body = _build_demo_invitation_html(
        recipient_name=recipient_name,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        description=description,
        calendar_link=calendar_link,
    )

    try:
        await _send_email(to=to_email, subject=subject, html_body=html_body)
        logger.info("[email_service] Email sent successfully to %s", to_email)
    except Exception as exc:
        logger.error("[email_service] Error sending email via SMTP: %s", exc)
        raise EmailServiceError(f"Failed to send email to {to_email}: {exc}") from exc
