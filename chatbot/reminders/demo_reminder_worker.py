"""Demo reminder worker — notifies users about upcoming demos."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from chatbot.ai_agent.reminder_localizer import localize_notification
from chatbot.db.services import services
from chatbot.services.channel_router import send_to_user

logger = logging.getLogger(__name__)

REMINDER_WINDOW_MINUTES: int = 60


async def run() -> None:
    """Execute one pass of the demo reminder worker."""
    logger.info("[demo_reminder_worker] Starting run")
    now = datetime.now(UTC).replace(tzinfo=None)
    window_end = now + timedelta(minutes=REMINDER_WINDOW_MINUTES)

    all_users = await services.get_all_users()
    processed = 0

    for user in all_users:
        phone: str = user.phone

        demo = await services.get_demo_by_phone(phone)
        if not demo:
            continue

        scheduled_at = demo.scheduled_at
        if not scheduled_at:
            continue

        # Check if demo is within the next 60 minutes
        if scheduled_at > window_end or scheduled_at < now:
            continue

        # Check if reminder was already sent
        if demo.upcoming_reminder_sent_at is not None:
            continue

        # Calculate minutes until demo
        minutes_until = int((scheduled_at - now).total_seconds() / 60)

        nombre = getattr(user, "name", None) or "amigo/a"
        raw_message = (
            f"¡Hola {nombre}! Tu demo de Viventi es en {minutes_until} minutos. "
            f"¡Te esperamos! 🗓"
        )

        # Localize to user's language
        try:
            messages = await services.get_recent_messages(phone, hours=72)
            history: list[str] = [f"{msg.role}: {msg.message}" for msg in messages]
            localized_message = await localize_notification(history, raw_message)
        except Exception as exc:
            logger.error(
                "[demo_reminder_worker] Localization failed for %s: %s", phone, exc
            )
            localized_message = raw_message

        # Send reminder
        try:
            await send_to_user(phone, localized_message)
        except Exception as exc:
            logger.error(
                "[demo_reminder_worker] Failed to send reminder to %s: %s",
                phone,
                exc,
            )
            continue

        # Mark reminder as sent
        await services.mark_demo_reminder_sent(phone, now)

        processed += 1
        logger.info(
            "[demo_reminder_worker] Sent upcoming demo reminder to %s (demo in %d min)",
            phone,
            minutes_until,
        )

    logger.info("[demo_reminder_worker] Completed — processed %d users", processed)
