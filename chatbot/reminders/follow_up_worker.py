"""Follow-up worker — sends reminders to PHASE_3 users who haven't scheduled a demo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from chatbot.ai_agent.reminder_localizer import localize_notification
from chatbot.db.services import services
from chatbot.domain.conversation_states import ConversationState
from chatbot.services.channel_router import send_to_user
from chatbot.services.conversation_state_service import conversation_state_service
from chatbot.services.google_sheets_sync import sync_user_to_sheets

logger = logging.getLogger(__name__)

INACTIVITY_THRESHOLD_HOURS: int = 4
MAX_FOLLOW_UPS: int = 3

_FOLLOW_UP_TEMPLATES: list[str] = [
    (
        "Hola {nombre}, soy Vivi de Viventi. "
        "Quedamos en que ibas a pensar en agendar la demo. "
        "¿Hay alguna duda que te pueda responder antes?"
    ),
    (
        "{nombre}, un recordatorio rápido. "
        "Una sola reserva que hoy se pierde fuera de horario ya cubre el mes de Viventi. "
        "¿Agendamos 30 minutos esta semana?"
    ),
    (
        "Último mensaje de mi parte, {nombre}. "
        "Si en algún momento querés ver cómo funciona, estoy acá. "
        "Éxito con {nombre_establecimiento} 🍀"
    ),
]


async def run() -> None:
    """Execute one pass of the follow-up worker."""
    logger.info("[follow_up_worker] Starting run")
    now = datetime.now(UTC).replace(tzinfo=None)
    threshold = now - timedelta(hours=INACTIVITY_THRESHOLD_HOURS)

    # Get users who had recent activity (within last 7 days to catch all PHASE_3 users)
    all_users = await services.get_all_users()
    processed = 0

    for user in all_users:
        phone: str = user.phone
        state_value: str = getattr(user, "conversation_state", "PHASE_1")

        if state_value != ConversationState.PHASE_3.value:
            continue

        # Check if user has a scheduled demo — if so, skip
        demo = await services.get_demo_by_phone(phone)
        if demo:
            continue

        last_interaction = getattr(user, "last_interaction", None)
        if not last_interaction or last_interaction > threshold:
            continue  # Active recently, no follow-up needed

        follow_up_count: int = getattr(user, "follow_up_count", 0) or 0
        last_follow_up_at = getattr(user, "last_follow_up_at", None)

        # If already sent 3 follow-ups and still inactive > 4h → transition to LOST
        if follow_up_count >= MAX_FOLLOW_UPS:
            logger.info(
                "[follow_up_worker] %s: %d follow-ups sent, inactive > 4h → LOST",
                phone,
                follow_up_count,
            )
            try:
                await conversation_state_service.phase_3_to_lost(phone)
            except Exception as exc:
                logger.error(
                    "[follow_up_worker] Failed to transition %s to LOST: %s",
                    phone,
                    exc,
                )
            continue

        # Check if enough time has passed since last follow-up
        if last_follow_up_at and last_follow_up_at > threshold:
            continue  # Too soon since last follow-up

        # Select template and send follow-up
        template_idx = min(follow_up_count, len(_FOLLOW_UP_TEMPLATES) - 1)
        template = _FOLLOW_UP_TEMPLATES[template_idx]

        nombre = getattr(user, "name", None) or "amigo/a"
        nombre_establecimiento = (
            getattr(user, "establishment_name", None)
            or getattr(user, "experience_name", None)
            or "tu experiencia"
        )
        raw_message = template.format(
            nombre=nombre,
            nombre_establecimiento=nombre_establecimiento,
        )

        # Localize the message to user's language
        try:
            messages = await services.get_recent_messages(phone, hours=72)
            history: list[str] = [f"{msg.role}: {msg.message}" for msg in messages]
            localized_message = await localize_notification(history, raw_message)
        except Exception as exc:
            logger.error(
                "[follow_up_worker] Localization failed for %s: %s", phone, exc
            )
            localized_message = raw_message

        # Send via appropriate channel
        try:
            await send_to_user(phone, localized_message)
        except Exception as exc:
            logger.error(
                "[follow_up_worker] Failed to send follow-up to %s: %s", phone, exc
            )
            continue

        # Update follow-up tracking
        new_count = follow_up_count + 1
        await services.update_user(
            phone,
            follow_up_count=new_count,
            last_follow_up_at=now,
        )

        # Sync to Google Sheets with updated follow-up state
        try:
            await sync_user_to_sheets(phone)
        except Exception as exc:
            logger.error("[follow_up_worker] Sheets sync failed for %s: %s", phone, exc)

        processed += 1
        logger.info("[follow_up_worker] Sent follow-up #%d to %s", new_count, phone)

    logger.info("[follow_up_worker] Completed — processed %d users", processed)
