"""Gmail API service — sends transactional emails via OAuth 2.0.

Uses a pre-authorized token (gmail_token.json) generated once with
scripts/authorize_gmail.py. The token is refreshed automatically when
it expires.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from chatbot.core.config import config

logger = logging.getLogger(__name__)

SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.send"]


class GmailServiceError(Exception):
    """Raised when the Gmail API returns an unexpected error."""


def _get_gmail_service():
    """Build and return an authorized Gmail API service instance."""
    creds = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


async def _run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


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
    """Send a demo invitation email via Gmail API.

    Args:
        to_email: Recipient email address.
        recipient_name: Recipient's first name for personalization.
        scheduled_at: Demo datetime (timezone-aware).
        duration_minutes: Duration of the demo in minutes.
        description: Short description of what will be covered.
        calendar_link: Google Calendar event HTML link.

    Raises:
        GmailServiceError: If the Gmail API returns an error.
    """
    logger.info("[gmail_service] Sending demo invitation to %s", to_email)

    formatted_date = scheduled_at.strftime("%d/%m/%Y a las %H:%M")
    subject = f"Tu demo de Viventi — {formatted_date} hs"

    html_body = _build_demo_invitation_html(
        recipient_name=recipient_name,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        description=description,
        calendar_link=calendar_link,
    )

    message = MIMEMultipart("alternative")
    message["to"] = to_email
    message["from"] = config.GMAIL_SENDER
    message["subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service = _get_gmail_service()

    def _send():
        return service.users().messages().send(userId="me", body={"raw": raw}).execute()

    try:
        result = await _run_in_executor(_send)
    except HttpError as exc:
        raise GmailServiceError(f"Failed to send email to {to_email}: {exc}") from exc

    logger.info(
        "[gmail_service] Email sent to %s message_id=%s",
        to_email,
        result.get("id"),
    )
