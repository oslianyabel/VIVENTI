"""Dynamic instructions registered on the VIVENTI agent at init time."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic_ai import Agent, RunContext

from chatbot.ai_agent.dependencies import AgentDeps

logger = logging.getLogger(__name__)


def register_instructions(agent: Agent[AgentDeps, str]) -> None:
    """Register all dynamic @instructions on the given agent."""

    @agent.instructions
    def reply_in_user_language(
        ctx: RunContext[AgentDeps],
    ) -> str:
        return (
            "Always reply in the same language as the user's most recent message. "
            "Ignore the language used by this system prompt, tool schemas, tool outputs, "
            "or ERP data. If any tool returns content in a different language, translate "
            "or adapt it before answering. If the user writes in Spanish, use Rioplatense Spanish."
        )

    @agent.instructions
    def current_datetime(
        ctx: RunContext[AgentDeps],
    ) -> str:
        now = datetime.now(tz=timezone.utc).astimezone()
        return (
            f"Current date and time: {now.strftime('%A %d %B %Y, %H:%M')} "
            f"(server timezone: {now.strftime('%Z %z')}). "
            "Use this date to resolve expressions such as tomorrow, next week, next month, "
            "or in N days."
        )

    @agent.instructions
    async def inject_conversation_state(
        ctx: RunContext[AgentDeps],
    ) -> str:
        from chatbot.services.conversation_state_service import (
            conversation_state_service,
        )

        state = await conversation_state_service.get_state(ctx.deps.user_phone)
        return f"Estado actual de la conversación: {state.value}"

    @agent.instructions
    async def inject_user_data(
        ctx: RunContext[AgentDeps],
    ) -> str:
        from chatbot.db.services import services

        user = await services.get_user(ctx.deps.user_phone)
        if not user:
            return "No hay datos del usuario en la BD."

        known: dict[str, Any] = {}
        for attr in [
            "name",
            "email",
            "experience_name",
            "establishment_name",
            "experience_type",
            "country",
            "reservation_method",
            "monthly_reservations",
            "payment_method",
            "has_instagram",
            "uses_instagram_for_sales",
            "main_pain_point",
            "phase_2_answer_1",
            "phase_2_answer_2",
            "phase_2_answer_3",
            "phase_2_answer_4",
            "phase_2_answer_5",
            "phase_2_answer_6",
            "is_qualified",
            "language",
            "notes",
        ]:
            val = getattr(user, attr, None)
            if val is not None:
                known[attr] = val

        if not known:
            return "No hay datos personales del usuario en BD."
        pairs = [f"{k}: {v}" for k, v in known.items()]
        return "Datos conocidos del usuario:\n" + "\n".join(pairs)

    @agent.instructions
    async def inject_demo_data(
        ctx: RunContext[AgentDeps],
    ) -> str:
        from chatbot.db.services import services

        demo = await services.get_demo_by_phone(ctx.deps.user_phone)
        if not demo:
            return "El usuario no tiene demo agendada."
        dt = demo.scheduled_at
        return (
            f"Demo agendada: {demo.title} — "
            f"{dt.strftime('%d/%m/%Y %H:%M')} — "
            f"{demo.duration_minutes} min"
        )
