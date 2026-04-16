# uv run pytest -s chatbot/tests/test_gmail_service.py
"""Integration tests for Gmail service — real API calls.

These tests send actual emails via the Gmail API using the pre-authorized
token. Run manually to verify email delivery.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from chatbot.services.gmail_service import send_demo_invitation

logger = logging.getLogger(__name__)

CALENDAR_TZ = ZoneInfo("America/Montevideo")


# uv run pytest -s chatbot/tests/test_gmail_service.py::test_send_demo_invitation_email
@pytest.mark.asyncio
async def test_send_demo_invitation_email() -> None:
    """send_demo_invitation should send an email without raising errors.

    Check osliani_freelance@proton.me inbox to verify delivery.
    """
    to_email = "osliani_freelance@proton.me"
    scheduled_at = datetime(2026, 4, 25, 10, 0, tzinfo=CALENDAR_TZ)

    await send_demo_invitation(
        to_email=to_email,
        recipient_name="Osliani",
        scheduled_at=scheduled_at,
        duration_minutes=30,
        description=(
            "Vamos a ver cómo automatizar los mensajes que llegan por WhatsApp e Instagram "
            "y cómo manejar el sistema de señas para eventos."
        ),
        calendar_link="https://www.google.com/calendar/event?eid=test_event_id",
    )

    print(f"[OK] Demo invitation email sent to {to_email}. Check inbox.")
