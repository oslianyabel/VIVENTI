"""Google Calendar agent tools — thin wrappers around the Calendar service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.db.services import services
from chatbot.domain.demo import DemoRecord
from chatbot.services import conversation_state_service
from chatbot.services.google_calendar_service import (
    DEMO_DURATION_MINUTES,
    GoogleCalendarError,
)
from chatbot.services.google_calendar_service import cancel_event as _cancel_event
from chatbot.services.google_calendar_service import create_event as _create_event
from chatbot.services.google_calendar_service import (
    find_available_slots as _find_slots,
)
from chatbot.services.google_calendar_service import update_event as _update_event

logger = logging.getLogger(__name__)


async def get_available_slots(
    ctx: RunContext[AgentDeps],
    date: str,
) -> str:
    """Get available 30-minute demo slots for a given date.

    Use this tool to check calendar availability before scheduling a demo.
    The date must be in YYYY-MM-DD format.

    Args:
        ctx: Agent run context (injected automatically).
        date: Target date in YYYY-MM-DD format.

    Returns:
        Formatted list of available time slots, or a message if none available.
    """
    logger.info("[get_available_slots] date=%s", date)
    try:
        from chatbot.services.google_calendar_service import CALENDAR_TZ

        target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=CALENDAR_TZ)
    except ValueError:
        raise ModelRetry("Formato de fecha inválido. Usa YYYY-MM-DD (ej: 2025-03-15).")

    day_start = target.replace(hour=0, minute=0, second=0)
    day_end = day_start + timedelta(days=1)

    try:
        slots = await _find_slots(day_start, day_end)
    except GoogleCalendarError as exc:
        logger.error("[get_available_slots] %s", exc)
        return f"Error al consultar disponibilidad: {exc}"

    if not slots:
        return f"No hay horarios disponibles para el {date}."

    lines: list[str] = [f"Horarios disponibles para el {date}:"]
    for slot in slots:
        lines.append(f"• {slot.strftime('%H:%M')} hs")
    return "\n".join(lines)


async def create_google_calendar_event(
    ctx: RunContext[AgentDeps],
    title: str,
    description: str,
    scheduled_at: str,
    attendee_email: str | None = None,
) -> str:
    """Create a demo event in Google Calendar and transition to COMPLETED.

    Use this tool after the user confirms the demo date and time.
    The scheduled_at must be in ISO 8601 format (YYYY-MM-DDTHH:MM).

    Args:
        ctx: Agent run context (injected automatically).
        title: Event title, e.g. "Demo Viventi — Juan / Bodega Nara".
        description: Event description with experience details.
        scheduled_at: Demo datetime in ISO 8601 format.
        attendee_email: Optional attendee email.

    Returns:
        Confirmation message with the scheduled date and time.
    """
    phone = ctx.deps.user_phone
    logger.info(
        "[create_google_calendar_event] phone=%s title=%s scheduled_at=%s",
        phone,
        title,
        scheduled_at,
    )

    from chatbot.domain.conversation_states import ConversationState

    state = await conversation_state_service.get_state(phone)
    if state not in {
        ConversationState.PHASE_3,
        ConversationState.LOST,
        ConversationState.COMPLETED,
    }:
        raise ModelRetry(
            f"La conversación está en {state.value}. "
            "Solo se puede crear una demo cuando el estado es PHASE_3, LOST o COMPLETED."
        )

    # Si ya existe una demo en COMPLETED, cancelar el evento viejo primero
    if state == ConversationState.COMPLETED:
        existing_demo = await services.get_demo_by_phone(phone)
        if existing_demo and existing_demo.google_calendar_event_id:
            try:
                await _cancel_event(existing_demo.google_calendar_event_id)
                logger.info(
                    "[create_google_calendar_event] Cancelled old event %s before recreating",
                    existing_demo.google_calendar_event_id,
                )
            except GoogleCalendarError:
                pass  # El evento viejo puede no existir ya

    try:
        dt = datetime.fromisoformat(scheduled_at)
        if dt.tzinfo is None:
            from chatbot.services.google_calendar_service import CALENDAR_TZ

            dt = dt.replace(tzinfo=CALENDAR_TZ)
    except ValueError:
        raise ModelRetry(
            "Formato de fecha inválido. Usa ISO 8601 (ej: 2025-03-15T10:00)."
        )

    demo = DemoRecord(
        title=title,
        duration_minutes=DEMO_DURATION_MINUTES,
        description=description,
        user_phone=phone,
        scheduled_at=dt,
    )

    try:
        event_id = await _create_event(demo, attendee_email)
    except GoogleCalendarError as exc:
        logger.error("[create_google_calendar_event] %s", exc)
        raise ModelRetry(
            f"Error al crear el evento en Google Calendar: {exc}. "
            "Reintentá la creación del evento."
        )

    demo.google_calendar_event_id = event_id
    await services.upsert_demo(demo)

    if state == ConversationState.LOST:
        await conversation_state_service.lost_to_completed(phone)
    elif state == ConversationState.PHASE_3:
        await conversation_state_service.phase_3_to_completed(phone)
    # Si ya estaba en COMPLETED, no se necesita transición

    return (
        f"Demo agendada para el {dt.strftime('%d/%m/%Y a las %H:%M')} hs. "
        f"Duración: {DEMO_DURATION_MINUTES} minutos. "
        "Estado actualizado a COMPLETED automáticamente. No llames ninguna otra herramienta de transición."
    )


async def update_google_calendar_event(
    ctx: RunContext[AgentDeps],
    new_datetime: str,
) -> str:
    """Reschedule an existing demo to a new date and time.

    Use this tool when the user wants to change their demo schedule.
    The new_datetime must be in ISO 8601 format (YYYY-MM-DDTHH:MM).

    Args:
        ctx: Agent run context (injected automatically).
        new_datetime: New demo datetime in ISO 8601 format.

    Returns:
        Confirmation message with the new scheduled date and time.
    """
    phone = ctx.deps.user_phone
    logger.info("[update_google_calendar_event] phone=%s new=%s", phone, new_datetime)

    existing = await services.get_demo_by_phone(phone)
    if not existing:
        raise ModelRetry("No hay demo agendada para este usuario.")

    try:
        new_dt = datetime.fromisoformat(new_datetime)
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ModelRetry(
            "Formato de fecha inválido. Usa ISO 8601 (ej: 2025-03-15T10:00)."
        )

    event_id = existing.google_calendar_event_id
    if not event_id:
        raise ModelRetry("La demo no tiene un evento asociado en Google Calendar.")

    demo = DemoRecord(
        title=existing.title,
        duration_minutes=existing.duration_minutes,
        description=existing.description,
        user_phone=phone,
        scheduled_at=new_dt,
        google_calendar_event_id=event_id,
    )

    try:
        await _update_event(event_id, new_dt, demo)
    except GoogleCalendarError as exc:
        logger.error("[update_google_calendar_event] %s", exc)
        return f"Error al actualizar el evento: {exc}"

    demo.upcoming_reminder_sent_at = None
    await services.upsert_demo(demo)

    return f"Demo re-agendada para el {new_dt.strftime('%d/%m/%Y a las %H:%M')} hs."


async def cancel_google_calendar_event(
    ctx: RunContext[AgentDeps],
) -> str:
    """Cancel the user's scheduled demo and transition to LOST.

    Use this tool when the user explicitly asks to cancel their demo.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation that the demo was cancelled.
    """
    phone = ctx.deps.user_phone
    logger.info("[cancel_google_calendar_event] phone=%s", phone)

    from chatbot.domain.conversation_states import ConversationState

    state = await conversation_state_service.get_state(phone)
    if state != ConversationState.COMPLETED:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en COMPLETED. "
            "Solo se puede cancelar una demo cuando el estado es COMPLETED."
        )

    existing = await services.get_demo_by_phone(phone)
    if not existing:
        raise ModelRetry("No hay demo agendada para este usuario.")

    event_id = existing.google_calendar_event_id
    if event_id:
        try:
            await _cancel_event(event_id)
        except GoogleCalendarError as exc:
            logger.error("[cancel_google_calendar_event] %s", exc)

    await services.delete_demo_by_phone(phone)
    await conversation_state_service.completed_to_lost(phone)

    return "Demo cancelada exitosamente."


async def get_user_demo_scheduled(
    ctx: RunContext[AgentDeps],
) -> str:
    """Get details of the user's scheduled demo.

    Use this tool when the user asks about their scheduled demo.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Formatted demo details, or a message if no demo is scheduled.
    """
    phone = ctx.deps.user_phone
    logger.info("[get_user_demo_scheduled] phone=%s", phone)

    demo = await services.get_demo_by_phone(phone)
    if not demo:
        return "No hay demo agendada."

    dt = demo.scheduled_at
    return (
        f"Demo agendada:\n"
        f"• Título: {demo.title}\n"
        f"• Fecha: {dt.strftime('%d/%m/%Y a las %H:%M')} hs\n"
        f"• Duración: {demo.duration_minutes} minutos"
    )
