"""Shared message processing — pre/post-agent logic for all channels."""

from __future__ import annotations

import logging

from chatbot.db.services import services
from chatbot.domain.conversation_states import ConversationState
from chatbot.services.conversation_state_service import conversation_state_service
from chatbot.services.lead_orchestrator import re_evaluate_discard

logger = logging.getLogger(__name__)


async def pre_agent_processing(phone: str) -> None:
    """Execute pre-agent hooks before running the AI agent.

    1. Update last_interaction timestamp.
    2. If DISCARD, re-evaluate qualification automatically.

    Args:
        phone: User phone or chat ID.
    """
    await services.update_last_interaction(phone)

    state = await conversation_state_service.get_state(phone)

    if state == ConversationState.DISCARD:
        logger.info("[pre_agent] DISCARD user %s — re-evaluating", phone)
        messages = await services.get_recent_messages(phone, hours=72)
        context: list[str] = [f"{msg.role}: {msg.message}" for msg in messages]
        try:
            result = await re_evaluate_discard(phone, context)
            if result.qualifies:
                logger.info("[pre_agent] %s re-qualified → PHASE_3", phone)
        except Exception as exc:
            logger.error("[pre_agent] Re-evaluation failed for %s: %s", phone, exc)
